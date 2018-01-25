import multiprocessing as mulproc
import random as rand
import itertools as it

import numpy as np

from wepy.resampling.resamplers.resampler import Resampler
from wepy.resampling.scoring.scorer import AllToAllScorer
from wepy.resampling.decisions.clone_merge import MultiCloneMergeDecision

class WExplore2Resampler(Resampler):

    DECISION = MultiCloneMergeDecision

    def __init__(self, seed=None, pmin=1e-12, pmax=0.1, dpower=4, merge_dist=2.5,
                 scorer=None):

        self.decision = self.DECISION

        # the minimum probability for a walker
        self.pmin=pmin
        # ln(probability_min)
        self.lpmin = np.log(pmin/100)

        # maximum probability for a walker
        self.pmax=pmax

        # 
        self.dpower = dpower

        # 
        self.merge_dist = merge_dist

        # setting the random seed
        self.seed = seed
        if seed is not None:
            rand.seed(seed)

        # the scorer class that will perform the all-to-all distances
        # between walkers

        # assert issubclass(type(scorer), AllToAllScorer), "The
        # scorer class must be an AllToAllScorer class"
        self.scorer = scorer

    def _calcspread(self, walkerwt, amp, distance_matrix):

        n_walkers = len(walkerwt)
        # the value to be optimized
        spread = 0

        # 
        wsum = np.zeros(n_walkers)

        # weight factors for the walkers
        wtfac = np.zeros(n_walkers)

        # set the weight factors
        for i in range(n_walkers):

            if walkerwt[i] > 0 and amp[i] > 0:
                wtfac[i] = np.log(walkerwt[i]/amp[i]) - self.lpmin

            else:
                wtfac[i] = 0

            if wtfac[i] < 0:
                wtfac[i] = 0

        # 
        for i in range(n_walkers - 1):
            if amp[i] > 0:
                for j in range(i+1, n_walkers):
                    if amp[j] > 0:
                        d = ((distance_matrix[i][j])**self.dpower) * wtfac[i] * wtfac[j]
                        spread += d * amp[i] * amp[j]
                        wsum[i] += d * amp[j]
                        wsum[j] += d * amp[i]

        # another implementation for personal clarity
        # for i, j in it.combinations(range(len(n_walkers)), 2):
        #     if amp[i] > 0 and amp[j] > 0:
        #         d = ((distance_matrix[i][j])**self.dpower) * wtfac[i] * wtfac[j]
        #         spread += d * amp[i] * amp[j]
        #         wsum[i] = += d * amp[j]
        #         wsum[j] += d * amp[i]

        return spread, wsum

    def decide_clone_merge(self, walkerwt, amp, distance_matrix, debug_prints=False):

        n_walkers = len(walkerwt)

        spreads = []
        merge_groups = [[] for i in range(n_walkers)]
        walker_clone_nums = [0 for i in range(n_walkers)]

        new_wt = walkerwt.copy()
        new_amp = amp.copy()
        # initialize the actions to nothing, will be overwritten

        # calculate the initial spread which will be optimized
        spread, wsum = self._calcspread(walkerwt, new_amp, distance_matrix)
        spreads.append(spread)

        # maximize the variance through cloning and merging
        if debug_prints:
            print("Starting variance optimization:", spread)

        productive = True
        while productive:
            productive = False
            # find min and max wsums, alter new_amp
            minwind = None
            maxwind = None

            # selects a walker with minimum wsum and a walker with
            # maximum wsum walker (distance to other walkers) will be
            # tagged for cloning (stored in maxwind)
            max_tups = [(value, i) for i, value in enumerate(wsum)
                        if (new_amp[i] >= 1) and (new_wt[i]/(new_amp[i] + 1) > self.pmin)]

            if len(max_tups) > 0:
                maxvalue, maxwind = max(max_tups)

            # walker with the lowest wsum (distance to other walkers)
            # will be tagged for merging (stored in minwind)
            min_tups = [(value, i) for i,value in enumerate(wsum)
                        if new_amp[i] == 1 and (new_wt[i]  < self.pmax)]

            if len(min_tups) > 0:
                minvalue, minwind = min(min_tups)

            # does minwind have an eligible merging partner?
            closedist = self.merge_dist
            closewalk = None
            condition_list = np.array([i is not None for i in [minwind, maxwind]])
            if condition_list.all() and minwind != maxwind:

                closewalk_available = set(range(n_walkers)).difference([minwind, maxwind])
                closewalk_available = [idx for idx in closewalk_available
                                      if (new_amp[idx]==1) and
                                       (new_wt[idx] + new_wt[minwind] < self.pmax)
                                      ]

                if len(closewalk_available) > 0:
                    tups = [(distance_matrix[minwind][i], i) for i in closewalk_available
                                            if distance_matrix[minwind][i] < (self.merge_dist)]
                    if len(tups) > 0:
                        closedist, closewalk = min(tups)


            # did we find a closewalk?
            condition_list = np.array([i is not None for i in [minwind, maxwind, closewalk]])
            if condition_list.all() :

                # change new_amp
                tempsum = new_wt[minwind] + new_wt[closewalk]
                new_amp[minwind] = new_wt[minwind]/tempsum
                new_amp[closewalk] = new_wt[closewalk]/tempsum
                new_amp[maxwind] += 1

                # re-determine spread function, and wsum values
                newspread, wsum = self._calcspread(new_wt, new_amp, distance_matrix)

                if newspread > spread:
                    spreads.append(newspread)

                    if debug_prints:
                        print("Variance move to", newspread, "accepted")

                    productive = True
                    spread = newspread

                    # make a decision on which walker to keep
                    # (minwind, or closewalk), equivalent to:
                    # `random.choices([closewalk, minwind],
                    #                 weights=[new_wt[closewalk], new_wt[minwind])`
                    r = rand.uniform(0.0, new_wt[closewalk] + new_wt[minwind])

                     # keeps closewalk and gets rid of minwind
                    if r < new_wt[closewalk]:
                        keep_idx = closewalk
                        squash_idx = minwind

                    # keep minwind, get rid of closewalk
                    else:
                        keep_idx = minwind
                        squash_idx = closewalk

                    # update weight
                    new_wt[keep_idx] += new_wt[squash_idx]
                    new_wt[squash_idx] = 0.0

                    # update new_amps
                    new_amp[squash_idx] = 0
                    new_amp[keep_idx] = 1

                    # add the squash index to the merge group
                    merge_groups[keep_idx].append(squash_idx)

                    # add the indices of the walkers that were already
                    # in the merge group that was just squashed
                    merge_groups[keep_idx].extend(merge_groups[squash_idx])

                    # reset the merge group that was just squashed to empty
                    merge_groups[squash_idx] = []

                    # increase the number of clones that the cloned
                    # walker has
                    walker_clone_nums[maxwind] += 1

                    # new spread for starting new stage
                    newspread, wsum = self._calcspread(new_wt, new_amp, distance_matrix)
                    spreads.append(newspread)

                    if debug_prints:
                        print("variance after selection:", newspread)

                # if not productive
                else:
                    new_amp[minwind] = 1
                    new_amp[closewalk] = 1
                    new_amp[maxwind] -= 1

        # given we know what we want to clone to specific slots
        # (squashing other walkers) we need to determine where these
        # squashed walkers will be merged
        walker_actions = self.assign_merges(merge_groups, walker_clone_nums)

        return([walker_actions]), spreads[-1]

    def resample(self, walkers, debug_prints=False):

        n_walkers = len(walkers)
        walkerwt = [walker.weight for walker in walkers]
        amp = [1 for i in range(n_walkers)]

        # calculate distance matrix
        distance_matrix = self.scorer.score(walkers)

        if debug_prints:
            print("distance_matrix")
            print(np.array(distance_matrix))

        # determine cloning and merging actions to be performed, by
        # maximizing the spread, i.e. the Decider
        resampling_actions, spread = self.decide_clone_merge(walkerwt, amp, distance_matrix,
                                                             debug_prints=debug_prints)

        # actually do the cloning and merging of the walkers
        resampled_walkers = self.decision.action(walkers, resampling_actions)

        data = {'distance_matrix' : np.array(distance_matrix), 'spread' : np.array([spread]) }

        return resampled_walkers, resampling_actions, data
