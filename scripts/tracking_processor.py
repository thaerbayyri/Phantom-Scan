"""DBSCAN + Kalman target tracker (numpy/sklearn).

LEGACY/REFERENCE — the live pipeline uses the TypeScript port in
server/lib/tracking.ts; this Python original is kept for offline analysis.
Flow: cluster point-cloud points -> largest cluster centroid -> constant-
velocity Kalman filter -> smoothed position/velocity (movement) estimate.
"""
import numpy as np
import time
from sklearn.cluster import DBSCAN
from typing import List, Dict, Optional, Tuple

class KalmanFilter:
    """
    Constant Velocity Kalman Filter for 3D tracking.
    State: [x, y, z, vx, vy, vz]
    """
    def __init__(self, dt: float = 0.1):
        self.dt = dt
        
        # State vector [x, y, z, vx, vy, vz]
        self.x = np.zeros(6)
        
        # State Transition Matrix (F)
        self.F = np.eye(6)
        self.F[0, 3] = dt
        self.F[1, 4] = dt
        self.F[2, 5] = dt
        
        # Measurement Matrix (H) - we measure position only
        self.H = np.zeros((3, 6))
        self.H[0, 0] = 1
        self.H[1, 1] = 1
        self.H[2, 2] = 1
        
        # Covariance Matrix (P)
        self.P = np.eye(6) * 1.0
        
        # Process Noise Covariance (Q) - model uncertainty
        self.Q = np.eye(6) * 0.01
        
        # Measurement Noise Covariance (R) - sensor noise
        self.R = np.eye(3) * 0.1

    def predict(self):
        # x = Fx
        self.x = self.F @ self.x
        # P = FPF' + Q
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x

    def update(self, measurement: np.ndarray):
        # y = z - Hx (Innovation)
        z = np.array(measurement)
        y = z - self.H @ self.x
        
        # S = HPH' + R (Innovation Covariance)
        S = self.H @ self.P @ self.H.T + self.R
        
        # K = PH'S^-1 (Kalman Gain)
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # x = x + Ky
        self.x = self.x + K @ y
        
        # P = (I - KH)P
        I = np.eye(6)
        self.P = (I - K @ self.H) @ self.P

    def get_state(self):
        return {
            'x': self.x[0], 'y': self.x[1], 'z': self.x[2],
            'vx': self.x[3], 'vy': self.x[4], 'vz': self.x[5]
        }

class TrackingProcessor:
    def __init__(self):
        # DBSCAN parameters: eps=0.5m, min_samples=4
        self.clustering = DBSCAN(eps=0.5, min_samples=4)
        self.kf = KalmanFilter(dt=0.1) # Assuming ~10Hz update rate
        
        self.last_target = None
        self.consecutive_misses = 0
        self.max_misses = 5
        self.history = [] # Formatting for export if needed

    def process_frame(self, points: List[Dict]) -> Optional[Dict]:
        """
        Process a point cloud frame:
        1. Cluster points using DBSCAN with dynamic background subtraction (assumed upstream).
        2. Identify the 'Human Target' (largest cluster).
        3. Smooth trajectory with Kalman Filter.
        4. Return tracked target state.
        """
        
        # Convert points to numpy array
        if not points:
            return self._handle_miss()
            
        data = np.array([[p['x'], p['y'], p['z'], p.get('amplitude', 1.0)] for p in points])
        coords = data[:, :3]
        
        # 1. DBSCAN Clustering
        labels = self.clustering.fit_predict(coords)
        
        # 2. Identify Target (Largest Cluster)
        unique_labels = set(labels)
        if -1 in unique_labels:
            unique_labels.remove(-1) # Remove noise
            
        if not unique_labels:
            return self._handle_miss()
            
        best_cluster_label = -1
        max_energy = -1.0
        
        for label in unique_labels:
            mask = (labels == label)
            cluster_points = data[mask]
            # Energy = sum of amplitudes
            energy = np.sum(cluster_points[:, 3])
            
            if energy > max_energy:
                max_energy = energy
                best_cluster_label = label
                
        if best_cluster_label == -1:
            return self._handle_miss()
            
        # Compute Centroid (Weighted Center of Mass)
        target_indices = (labels == best_cluster_label)
        target_points = data[target_indices]
        
        weights = target_points[:, 3]
        total_weight = np.sum(weights)
        
        if total_weight == 0:
            return self._handle_miss()
            
        centroid = np.average(target_points[:, :3], axis=0, weights=weights)
        
        # 3. Kalman Filter Update
        self.kf.predict()
        self.kf.update(centroid)
        self.consecutive_misses = 0
        
        state = self.kf.get_state()
        
        target = {
            'timestamp': time.time(),
            'id': 1,
            'x': state['x'],
            'y': state['y'],
            'z': state['z'],
            'vx': state['vx'],
            'vy': state['vy'],
            'vz': state['vz'],
            'intensity': max_energy
        }
        
        self.last_target = target
        self.history.append(target)
        return target

    def _handle_miss(self):
        """Handle missing target (occlusion) by predicting with KF."""
        self.consecutive_misses += 1
        self.kf.predict() # Coasting
        
        if self.consecutive_misses <= self.max_misses and self.last_target:
            state = self.kf.get_state()
            return {
                **self.last_target,
                'x': state['x'],
                'y': state['y'],
                'z': state['z'],
                'vx': state['vx'],
                'vy': state['vy'],
                'vz': state['vz'],
                'intensity': self.last_target['intensity'] * 0.9 # Fade out
            }
            
        return None

    def save_tracking_session(self, filename="tracking_session.csv"):
        """Export trajectory data to CSV."""
        if not self.history:
            print("No tracking history to save.")
            return
            
        import csv
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.history[0].keys())
            writer.writeheader()
            writer.writerows(self.history)
        print(f"Session saved to {filename}")

# Example Usage
if __name__ == "__main__":
    processor = TrackingProcessor()
    
    # Simulated noisy point cloud (x, y, z, amp)
    frame1 = [
        {'x': 1.0, 'y': 0.5, 'z': 0.0, 'amplitude': 10},
        {'x': 1.1, 'y': 0.6, 'z': 0.1, 'amplitude': 8},
        {'x': 0.9, 'y': 0.5, 'z': 0.1, 'amplitude': 9},
        {'x': 1.0, 'y': 0.4, 'z': -0.1, 'amplitude': 7},
        {'x': 1.2, 'y': 0.7, 'z': 0.2, 'amplitude': 6}, # Valid cluster (5 points)
        {'x': 5.0, 'y': 5.0, 'z': 5.0, 'amplitude': 2}  # Noise (outlier)
    ]
    
    target = processor.process_frame(frame1)
    print("Tracked Target:", target)
    
    processor.save_tracking_session()
