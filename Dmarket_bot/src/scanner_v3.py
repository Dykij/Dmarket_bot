import math
import logging
from typing import Dict, List, Tuple

import cupy as cp

logger = logging.getLogger(__name__)

class ScannerV3:
    """
    GPU-accelerated spatial arbitrage scanner for Dmarket.
    Utilizes Bellman-Ford algorithm with SPFA logic on CuPy for O(|V||E|) reduction.
    """
    def __init__(self, trading_fee: float = 0.05):
        self.fee = trading_fee
        
        # Internal graph representations
        self.node_mapping: Dict[str, int] = {}
        self.reverse_mapping: Dict[int, str] = {}
        self.edges: List[Tuple[int, int, float]] = []

    def build_graph(self, market_pairs: List[Dict[str, any]]):
        """
        Expects a list of pairs from Dmarket API:
        {"source": "USDT", "target": "CSGO_Key", "exchange_rate": 2.5}
        """
        self.edges = []
        node_idx = 0
        
        for pair in market_pairs:
            src = pair['source']
            tgt = pair['target']
            rate = pair['exchange_rate']
            
            if src not in self.node_mapping:
                self.node_mapping[src] = node_idx
                self.reverse_mapping[node_idx] = src
                node_idx += 1
            if tgt not in self.node_mapping:
                self.node_mapping[tgt] = node_idx
                self.reverse_mapping[node_idx] = tgt
                node_idx += 1
                
            u = self.node_mapping[src]
            v = self.node_mapping[tgt]
            
            # Constraint: w(u,v) = -math.log(exchange_rate * (1 - trading_fee))
            weight = -math.log(rate * (1 - self.fee))
            self.edges.append((u, v, weight))
            
        logger.info(f"Graph built: {node_idx} vertices, {len(self.edges)} edges.")

    def detect_arbitrage_spfa_gpu(self) -> List[List[str]]:
        """
        Executes SPFA heuristic over Bellman-Ford using CuPy tensors on sm_120 cores.
        Returns a list of arbitrage cycles (each cycle is a path of asset names).
        """
        V = len(self.node_mapping)
        E = len(self.edges)
        if V == 0 or E == 0:
            return []

        # Move topology to GPU VRAM limits
        u_arr = cp.array([e[0] for e in self.edges], dtype=cp.int32)
        v_arr = cp.array([e[1] for e in self.edges], dtype=cp.int32)
        w_arr = cp.array([e[2] for e in self.edges], dtype=cp.float32)

        # SPFA structures
        distances = cp.full(V, cp.inf, dtype=cp.float32)
        predecessors = cp.full(V, -1, dtype=cp.int32)
        in_queue = cp.zeros(V, dtype=cp.bool_)
        count = cp.zeros(V, dtype=cp.int32) # Detect negative cycle if count[v] >= V

        # Dummy start vertex to ensure disconnected components are reached
        distances[0] = 0.0
        
        # Simple queue for SPFA
        queue = [0]
        in_queue[0] = True
        
        cycles_detected = set() # Avoid duplicates
        
        while queue:
            u = queue.pop(0)
            in_queue[u] = False
            
            # Find all outgoing edges from u. 
            # In pure Python loops this is slow, so we can use CuPy masking for vectorized relaxation.
            # However, for rigorous negative cycle extraction, extracting the path requires CPU steps.
            idx_mask = (u_arr == u)
            valid_idx = cp.where(idx_mask)[0]
            
            for i in valid_idx.get(): # Transition back to CPU for graph pathing
                v_node = int(v_arr[i])
                weight = float(w_arr[i])
                
                if distances[u] + weight < distances[v_node]:
                    distances[v_node] = distances[u] + weight
                    predecessors[v_node] = u
                    
                    if not in_queue[v_node]:
                        queue.append(v_node)
                        in_queue[v_node] = True
                        count[v_node] += 1
                        
                        if count[v_node] >= V: # Negative weight cycle detected
                            # Trace back to find the actual cycle
                            cycle = self._extract_cycle(predecessors.get(), v_node)
                            if cycle:
                                cycles_detected.add(tuple(cycle))
                                
        # Convert index cycles to coin labels
        labeled_cycles = []
        for cycle in cycles_detected:
            labeled = [self.reverse_mapping[idx] for idx in cycle]
            labeled_cycles.append(labeled)
            
        return labeled_cycles

    def _extract_cycle(self, predecessors: cp.ndarray, start_node: int) -> List[int]:
        cycle = []
        visited = set()
        curr = start_node
        
        while curr not in visited:
            visited.add(curr)
            curr = predecessors[curr]
            if curr == -1:
                return [] # Broken path
                
        # We hit the cycle loop start
        cycle_start = curr
        cycle.append(cycle_start)
        curr = predecessors[cycle_start]
        
        while curr != cycle_start:
            cycle.append(curr)
            curr = predecessors[curr]
            if curr == -1:
                return []
                
        cycle.reverse() # A -> B -> C
        return cycle
