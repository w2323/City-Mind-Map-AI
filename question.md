# Ambulance Placement Duplication

**Question:** 
There are some issues where ambulance placement is duplicated for node `H8`. Why is that?

**Answer:**
The duplication occurred because the Genetic Algorithm (GA) for ambulance placement was initializing and mutating its chromosomes using sampling **with** replacement (e.g., `random.choices`). This meant the algorithm allowed multiple ambulances to be assigned to the exact same depot node.

Because the GA's fitness function evaluates the *worst-case* response time across the entire city (minimax), piling all ambulances at a single optimal central depot (like `H8`) didn't technically worsen the absolute worst-case metric from the solver's perspective. Thus, the GA drifted toward clustering them there instead of spreading them out.

**The Fix:**
The placement logic was updated to enforce uniqueness:
1. **Initialization**: Switched to `random.sample` (without replacement) so initial chromosomes always feature distinct depots.
2. **Crossover**: Updated to pool unique genes from parents and sample unique sets for the children.
3. **Mutation**: Candidates are now explicitly filtered to only include depots that are not already present in the current chromosome.

With exactly 3 depots available and 3 ambulances to place, the GA now correctly distributes exactly one ambulance to each distinct depot (e.g., `['D11', 'E6', 'H8']`).
