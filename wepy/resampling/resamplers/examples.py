from wepy.resampling.resamplers.resampler import Resampler

# for the framework
from wepy.resampling.deciders.clone_merge import RandomCloneMergeDecider
from wepy.resampling.novelty.novelty import RandomNoveltyAssigner

# for the monolithic resampler
import random as rand
from wepy.resampling.decisions.clone_merge import CloneMergeDecision

class RandomCloneMergeResampler(Resampler):
    """WIP do not use!!! Example of a resampler that uses the
    Novelty->Decider framework, although the novelties here don't
    effect the outcome.

    """

    def __init__(self):
        self.novelty = RandomNoveltyAssigner
        self.decider = RandomCloneMergeDecider



class RandomCloneMergeResamplerMonolithic(Resampler):

    """Example of a monolithic resampler that does not use any
    framework. Everything is implemented from scratch in this class,
    thus overriding everything in the super class.

    """

    # constants for the class
    DECISION = CloneMergeDecision
    MIN_N_WALKERS = 3

    def __init__(self, seed=None, n_resamplings=10):
        if seed is not None:
            self.seed = seed
            rand.seed(seed)
        self.n_resamplings = n_resamplings



    def resample(self, walkers, debug_prints=False):

        n_walkers = len(walkers)

        # check to make sure there is enough walkers to clone and merge
        if n_walkers < self.MIN_N_WALKERS:
            raise TypeError("There must be at least 3 walkers to do cloning and merging")


        # choose number of clone-merges between 1 and 10
        n_clone_merges = rand.randint(0, self.n_resamplings)

        if debug_prints:
            result_template_str = "|".join(["{:^10}" for i in range(n_walkers+1)])
            print("Number of clone-merges to perform: {}".format(n_clone_merges))

        resampling_actions = []
        for resampling_stage_idx in range(n_clone_merges):

            if debug_prints:
                print("Resampling Stage: {}".format(resampling_stage_idx))
                print("---------------------")


            # choose a random walker to clone
            clone_idx = rand.randint(0, len(walkers)-1)

            clone_walker = walkers[clone_idx]

            # clone the chosen walker
            clone_children = clone_walker.clone()

            # choose a destination slot (index in the list) to put the clone in
            # the walker occupying that slot will be squashed
            # can't choose the same slot it is in
            squash_available = set(range(n_walkers)).difference({clone_idx})
            squash_idx = rand.choice([walker_idx for walker_idx in squash_available])
            squash_walker = walkers[squash_idx]

            # find a random merge target that is not either of the
            # cloned walkers
            merge_available = set(range(n_walkers)).difference({clone_idx, squash_idx})
            merge_idx = rand.choice([walker_idx for walker_idx in merge_available])
            merge_walker = walkers[merge_idx]

            # merge the squashed walker with the keep_merge walker
            merged_walker = squash_walker.squash(merge_walker)

            # make a new list of walkers
            resampled_walkers = []
            for idx, walker in enumerate(walkers):
                if idx == clone_idx:
                    # put one of the cloned walkers in the cloned one's place
                    resampled_walkers.append(clone_children.pop())
                elif idx == squash_idx:
                    # put one of the clone children in the squashed one's place
                    resampled_walkers.append(clone_children.pop())
                elif idx == merge_idx:
                    # put the merged walker in the keep_merged walkers place
                    resampled_walkers.append(merged_walker)
                else:
                    # if they did not move put them back where they were
                    resampled_walkers.append(walker)

            # reset the walkers for the next step as the resampled walkers
            walkers = resampled_walkers

            # make the decision records for this stage of resampling
            # initialize to RandomCloneMergeDecision.NOTHING, and their starting index
            walker_actions = [self.DECISION.record(self.DECISION.ENUM.NOTHING.value, (i,)) for
                              i in range(n_walkers)]

            # for the cloned one make a record for the instruction
            walker_actions[clone_idx] = self.DECISION.record(self.DECISION.ENUM.CLONE.value,
                                                             (clone_idx, squash_idx,))

            # for the squashed walker
            walker_actions[squash_idx] = self.DECISION.record(self.DECISION.ENUM.SQUASH.value,
                                                             (merge_idx,))

            # for the keep-merged walker
            walker_actions[merge_idx] = self.DECISION.record(self.DECISION.ENUM.KEEP_MERGE.value,
                                                             (merge_idx,))

            resampling_actions.append(walker_actions)

            # if debug_prints:

            #     # walker slot indices
            #     slot_str = result_template_str.format("slot", *[i for i in range(n_walkers)])
            #     print(slot_str)

            #     # the resampling actions
            #     decisions = []
            #     instructions = []
            #     for rec in walker_actions:
            #         decisions.append(str(rec.decision.name))
            #         if rec.decision is self.DECISION.ENUM.CLONE:
            #             instructions.append(str(",".join([str(i) for i in rec.instruction])))
            #         else:
            #             instructions.append(str(rec.instruction))

            #     decision_str = result_template_str.format("decision", *decisions)
            #     instruction_str = result_template_str.format("instruct", *instructions)
            #     print(decision_str)
            #     print(instruction_str)

            #     # print the state of the walkers at this stage of resampling
            #     walker_state_str = result_template_str.format("state",
            #         *[str(walker.state) for walker in resampled_walkers])
            #     print(walker_state_str)
            #     walker_weight_str = result_template_str.format("weight",
            #         *[str(walker.weight) for walker in resampled_walkers])
            #     print(walker_weight_str)


        # return values: resampled_walkers, resampler_records, resampling_data
        # we return no extra data from this resampler
        if n_clone_merges == 0:
            return walkers, [], {}
        else:
            # return the final state of the resampled walkers after all
            # stages, and the records of resampling
            return resampled_walkers, resampling_actions, {}
