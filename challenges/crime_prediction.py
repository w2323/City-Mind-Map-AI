# crime_prediction.py — Challenge 5: Crime Risk Prediction
# K-Means clustering (unsupervised) + Decision Tree (supervised classification)
#
# Pipeline:
#   1. Feature engineering: population density + industrial proximity
#   2. K-Means clustering (k=3) to discover natural groupings
#   3. Synthetic crime dataset generation using cluster + rule-based labels
#   4. Decision Tree classifier to predict HIGH / MEDIUM / LOW risk
#   5. Update graph node risk levels → affects edge costs globally
#
# Decision Tree chosen over KNN for better interpretability:
#   - Explainable feature splits and thresholds
#   - Easy to defend in viva ("if pop_density > 0.5 AND industrial_proximity > 0.3 → HIGH")
#   - No distance computation at prediction time
#
# All algorithms implemented from scratch — no sklearn.

import math
import random
from collections import Counter
from core.city_graph import CityGraph
from config.simulation_config import SimConfig


# ──────────────────────────────────────────────────────────
# Euclidean distance helper
# ──────────────────────────────────────────────────────────
def euclidean(a: list, b: list) -> float:
    """Euclidean distance between two feature vectors."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# ──────────────────────────────────────────────────────────
# Feature Engineering
# f1 = normalized population density (0 to 1)
# f2 = industrial proximity (reciprocal of Dijkstra distance)
# ──────────────────────────────────────────────────────────
def compute_features(graph: CityGraph) -> dict:
    """
    Compute feature vectors for all nodes.
    Returns {node_id: [f1, f2]} where:
        f1 = population / 200 (normalized density)
        f2 = 1 / (min_distance_to_industrial + 1) (proximity)
    """
    industrials = [n.id for n in graph.get_nodes_of_type(SimConfig.INDUSTRIAL)]

    # Compute minimum Dijkstra distance from each node to nearest industrial zone
    ind_dist = {nid: float("inf") for nid in graph.nodes}
    for ind_id in industrials:
        d = graph.dijkstra(ind_id)
        for nid, dist in d.items():
            if dist < ind_dist[nid]:
                ind_dist[nid] = dist

    features = {}
    for nid, node in graph.nodes.items():
        f1 = node.population / 200.0              # Normalized population density
        f2 = 1.0 / (ind_dist[nid] + 1.0)         # Industrial proximity (higher = closer)
        features[nid] = [f1, f2]
    return features


# ──────────────────────────────────────────────────────────
# K-Means Clustering — from scratch
# ──────────────────────────────────────────────────────────
class KMeans:
    """
    K-Means clustering algorithm (unsupervised).
    Groups nodes into k clusters based on feature similarity.
    """

    def __init__(self, k: int = None, max_iter: int = None):
        self.k = k or SimConfig.KMEANS_K
        self.max_iter = max_iter or SimConfig.KMEANS_MAX_ITER
        self.centroids: list = []
        self.labels: dict = {}     # node_id -> cluster_index

    def fit(self, features: dict):
        """
        Fit K-Means to the feature data.
        features: {node_id: [f1, f2]}
        """
        node_ids = list(features.keys())
        random.shuffle(node_ids)

        # Initialize centroids from k random data points
        self.centroids = [list(features[node_ids[i]]) for i in range(self.k)]

        for _ in range(self.max_iter):
            # Assignment step: assign each node to nearest centroid
            new_labels = {}
            for nid in node_ids:
                vec = features[nid]
                dists = [euclidean(vec, c) for c in self.centroids]
                new_labels[nid] = dists.index(min(dists))

            # Convergence check
            if new_labels == self.labels:
                break
            self.labels = new_labels

            # Update step: recompute centroids as cluster means
            for ci in range(self.k):
                cluster_vecs = [
                    features[nid] for nid, lbl in self.labels.items() if lbl == ci
                ]
                if cluster_vecs:
                    dims = len(cluster_vecs[0])
                    self.centroids[ci] = [
                        sum(v[d] for v in cluster_vecs) / len(cluster_vecs)
                        for d in range(dims)
                    ]
                else:
                    # Empty cluster: reset centroid to random point
                    self.centroids[ci] = list(features[random.choice(node_ids)])

    def predict(self, vec: list) -> int:
        """Predict cluster index for a feature vector."""
        dists = [euclidean(vec, c) for c in self.centroids]
        return dists.index(min(dists))


# ──────────────────────────────────────────────────────────
# Identify high-risk cluster (highest centroid feature sum)
# ──────────────────────────────────────────────────────────
def _identify_high_risk_cluster(kmeans: KMeans) -> int:
    """Find the cluster with highest combined population density + industrial proximity."""
    scores = [(c[0] + c[1], ci) for ci, c in enumerate(kmeans.centroids)]
    scores.sort(reverse=True)
    return scores[0][1]


# ──────────────────────────────────────────────────────────
# Synthetic Crime Dataset Generation
# ──────────────────────────────────────────────────────────
def generate_crime_dataset(graph: CityGraph, features: dict, kmeans: KMeans) -> list:
    """
    Generate labeled crime risk dataset using rule-based ground truth.
    Returns list of ([f1, f2], risk_label) tuples.
    Labels: "HIGH", "MEDIUM", "LOW"
    """
    dataset = []
    high_cluster = _identify_high_risk_cluster(kmeans)

    for nid, node in graph.nodes.items():
        f1, f2 = features[nid]
        cluster = kmeans.labels.get(nid, -1)

        # Rule-based risk assignment (synthetic ground truth)
        if node.node_type == SimConfig.INDUSTRIAL:
            label = "HIGH"
        elif cluster == high_cluster and f1 > 0.3:
            label = "HIGH"
        elif f1 > 0.5 and f2 > 0.2:
            label = "MEDIUM"
        elif f1 > 0.6:
            label = "MEDIUM"
        else:
            label = "LOW"

        dataset.append((features[nid], label))

    return dataset


# ──────────────────────────────────────────────────────────
# Decision Tree Classifier — from scratch
#
# Chosen over KNN for explainability:
#   - Each node in the tree represents a feature split with a threshold
#   - Easy to visualize and explain: "if pop_density > 0.5 → HIGH"
#   - No distance computation at prediction time
#   - Interpretable decision rules for viva defense
# ──────────────────────────────────────────────────────────
class DecisionTreeClassifier:
    """
    Decision Tree classifier implemented from scratch.
    Uses Gini impurity for splitting, with configurable max depth
    and minimum samples per leaf.
    """

    def __init__(self, max_depth: int = None, min_samples: int = None):
        self.max_depth = max_depth or SimConfig.DECISION_TREE_MAX_DEPTH
        self.min_samples = min_samples or SimConfig.DECISION_TREE_MIN_SAMPLES
        self.tree = None

    def fit(self, dataset: list):
        """
        Train the decision tree on the dataset.
        dataset: list of ([f1, f2, ...], label) tuples
        """
        self.tree = self._build_tree(dataset, depth=0)

    def predict(self, feature_vec: list) -> str:
        """Predict class label for a single feature vector."""
        return self._traverse(self.tree, feature_vec)

    # ── Gini Impurity ───────────────────────────────────────

    def _gini(self, groups: list, classes: list) -> float:
        """
        Calculate Gini impurity for a split.
        Gini = 1 - sum(p_i^2) for each class proportion p_i.
        Lower Gini = more pure split.
        """
        total = sum(len(g) for g in groups)
        if total == 0:
            return 0.0

        gini = 0.0
        for group in groups:
            size = len(group)
            if size == 0:
                continue
            score = 0.0
            for cls in classes:
                count = sum(1 for _, label in group if label == cls)
                proportion = count / size
                score += proportion ** 2
            gini += (1.0 - score) * (size / total)
        return gini

    # ── Find best split ─────────────────────────────────────

    def _best_split(self, dataset: list) -> dict:
        """
        Find the best feature and threshold to split the dataset.
        Tries all features and all unique values as potential thresholds.
        Returns dict with keys: feature_index, threshold, groups, gini
        """
        if not dataset:
            return None

        classes = list(set(label for _, label in dataset))
        n_features = len(dataset[0][0])

        best = {"gini": float("inf")}

        for feature_idx in range(n_features):
            # Get unique values for this feature
            values = sorted(set(vec[feature_idx] for vec, _ in dataset))

            # Try thresholds between consecutive unique values
            for i in range(len(values) - 1):
                threshold = (values[i] + values[i + 1]) / 2.0

                # Split dataset
                left = [(v, l) for v, l in dataset if v[feature_idx] <= threshold]
                right = [(v, l) for v, l in dataset if v[feature_idx] > threshold]

                if not left or not right:
                    continue

                gini = self._gini([left, right], classes)

                if gini < best["gini"]:
                    best = {
                        "feature_index": feature_idx,
                        "threshold": threshold,
                        "groups": (left, right),
                        "gini": gini,
                    }

        return best if "feature_index" in best else None

    # ── Build tree recursively ──────────────────────────────

    def _build_tree(self, dataset: list, depth: int) -> dict:
        """
        Recursively build the decision tree.
        Returns a tree node (dict) with either a split or a leaf prediction.
        """
        # Check stopping conditions
        labels = [label for _, label in dataset]
        if len(set(labels)) == 1:
            return {"leaf": True, "prediction": labels[0]}

        if depth >= self.max_depth or len(dataset) < self.min_samples:
            return {"leaf": True, "prediction": self._majority_vote(labels)}

        # Find best split
        split = self._best_split(dataset)
        if split is None or "feature_index" not in split:
            return {"leaf": True, "prediction": self._majority_vote(labels)}

        left_data, right_data = split["groups"]

        return {
            "leaf": False,
            "feature_index": split["feature_index"],
            "threshold": split["threshold"],
            "gini": split["gini"],
            "left": self._build_tree(left_data, depth + 1),
            "right": self._build_tree(right_data, depth + 1),
        }

    def _majority_vote(self, labels: list) -> str:
        """Return the most common label. Tie-break: HIGH > MEDIUM > LOW."""
        counts = Counter(labels)
        # Priority order for ties
        priority = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        return max(counts.keys(), key=lambda x: (counts[x], priority.get(x, 0)))

    # ── Prediction traversal ────────────────────────────────

    def _traverse(self, node: dict, feature_vec: list) -> str:
        """Traverse the tree to make a prediction."""
        if node["leaf"]:
            return node["prediction"]

        if feature_vec[node["feature_index"]] <= node["threshold"]:
            return self._traverse(node["left"], feature_vec)
        else:
            return self._traverse(node["right"], feature_vec)

    # ── Tree explanation (for viva) ─────────────────────────

    def explain(self, depth: int = 0, node: dict = None) -> str:
        """
        Generate human-readable decision rules.
        Useful for viva defense — shows exactly how predictions are made.
        """
        if node is None:
            node = self.tree
        if node is None:
            return "Tree not trained yet."

        indent = "  " * depth
        if node["leaf"]:
            return f"{indent}→ PREDICT: {node['prediction']}\n"

        feature_names = ["population_density", "industrial_proximity"]
        fname = feature_names[node["feature_index"]] if node["feature_index"] < len(feature_names) else f"feature_{node['feature_index']}"

        result = f"{indent}IF {fname} <= {node['threshold']:.3f} (gini={node['gini']:.3f}):\n"
        result += self.explain(depth + 1, node["left"])
        result += f"{indent}ELSE:\n"
        result += self.explain(depth + 1, node["right"])
        return result


# ──────────────────────────────────────────────────────────
# Full ML Pipeline — run once during initialization
# ──────────────────────────────────────────────────────────
def run_crime_risk_pipeline(graph: CityGraph) -> tuple:
    """
    Execute the complete crime risk prediction pipeline:
    1. Feature extraction (population density + industrial proximity)
    2. K-Means clustering (k=3)
    3. Synthetic crime dataset generation
    4. Decision Tree training
    5. Predict and update risk levels on all graph nodes
    6. Deploy police officers to highest-risk zones

    Returns (kmeans, decision_tree) for testing and inspection.

    IMPORTANT: Risk updates propagate globally.
    All subsequent edge cost calculations will use the updated risk multipliers.
    """
    # Step 1: Feature extraction
    features = compute_features(graph)

    # Step 2: K-Means clustering
    kmeans = KMeans()
    kmeans.fit(features)

    # Step 3: Generate synthetic crime dataset
    dataset = generate_crime_dataset(graph, features, kmeans)

    # Step 4: Train Decision Tree classifier
    dt = DecisionTreeClassifier()
    dt.fit(dataset)

    # Step 5: Predict risk for each node and update graph
    for nid in graph.nodes:
        predicted_risk = dt.predict(features[nid])
        risk_index = features[nid][0] + features[nid][1]  # Combined feature score
        graph.update_risk(nid, predicted_risk, risk_index)

    return kmeans, dt


# ──────────────────────────────────────────────────────────
# Police Officer Deployment
# The city has 10 police officers. They are allocated to the
# highest-risk zones based on predicted risk level and
# population density.
# ──────────────────────────────────────────────────────────
def deploy_police_officers(graph: CityGraph,
                           num_officers: int = None) -> list:
    """
    Deploy police officers to the highest-risk neighborhoods.

    Strategy:
        1. Rank all nodes by risk priority score:
           score = risk_weight * population_density
           where risk_weight = {HIGH: 3, MEDIUM: 2, LOW: 1}
        2. Assign officers to the top-N scoring nodes
        3. Each officer is assigned to a unique node

    This ensures officers are concentrated where they are most
    needed: high-risk areas with large populations.

    Args:
        graph: The shared city graph (with risk levels already set)
        num_officers: Number of officers to deploy (default: 10)

    Returns:
        List of (node_id, risk_level, priority_score) tuples
        representing officer assignments, sorted by priority.
    """
    if num_officers is None:
        num_officers = SimConfig.NUM_POLICE_OFFICERS

    risk_weights = {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "NONE": 0.5}

    # Score each node: risk_weight × population density
    scored_nodes = []
    for nid, node in graph.nodes.items():
        weight = risk_weights.get(node.risk_level, 0.5)
        score = weight * (node.population / 200.0)  # Normalized
        scored_nodes.append((nid, node.risk_level, round(score, 3)))

    # Sort by score descending — highest priority first
    scored_nodes.sort(key=lambda x: x[2], reverse=True)

    # Assign officers to top-N nodes
    deployments = scored_nodes[:num_officers]

    return deployments

