import sys
import os
import numpy as np

# Add parent directory to path to import the script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.csi_filter_pipeline import CSIFilterPipeline

def run_tests():
    print("=== Testing Occupancy Counting (Spatial Variance) ===")
    pipeline = CSIFilterPipeline()
    
    # Simulate an empty room (very low spatial variance)
    # 30 antennas/subcarriers (theta), 100 time samples (n)
    print("\nTest Case 1: Empty Room (Expected: 0 people)")
    empty_room = np.random.normal(loc=10.0, scale=0.1, size=(30, 100))
    count = pipeline.count_occupancy(empty_room)
    print(f"Result: {count} people counted.")
    assert count == 0, f"Failed Case 1: expected 0, got {count}"
    
    # Simulate 1 person (moderate variance)
    # We add a moving interference pattern that causes moderate spatial variance
    print("\nTest Case 2: One Person (Expected: 1 person)")
    one_person = np.random.normal(loc=10.0, scale=0.1, size=(30, 100))
    # Person causes a variance pattern over time across the antennas
    for t in range(100):
        one_person[:, t] += np.sin(np.linspace(0, 2 * np.pi, 30)) * 1.5 * np.sin(t * 0.1)
    
    count = pipeline.count_occupancy(one_person)
    print(f"Result: {count} people counted.")
    assert count == 1, f"Failed Case 2: expected 1, got {count}"
    
    # Simulate 2 people (higher variance)
    print("\nTest Case 3: Two People (Expected: 2 people)")
    two_people = np.random.normal(loc=10.0, scale=0.1, size=(30, 100))
    for t in range(100):
        # Two overlapping interference patterns
        pattern1 = np.sin(np.linspace(0, 4 * np.pi, 30)) * 2.5 * np.sin(t * 0.15)
        pattern2 = np.cos(np.linspace(0, 3 * np.pi, 30)) * 2.0 * np.cos(t * 0.08)
        two_people[:, t] += pattern1 + pattern2
        
    count = pipeline.count_occupancy(two_people)
    print(f"Result: {count} people counted.")
    assert count == 2, f"Failed Case 3: expected 2, got {count}"
    
    # Simulate 3 people (very high variance)
    print("\nTest Case 4: Three People (Expected: 3 people)")
    three_people = np.random.normal(loc=10.0, scale=0.1, size=(30, 100))
    for t in range(100):
        # Three chaotic interference patterns
        pattern1 = np.sin(np.linspace(0, 4 * np.pi, 30)) * 3.5 * np.sin(t * 0.2)
        pattern2 = np.cos(np.linspace(0, 5 * np.pi, 30)) * 3.0 * np.cos(t * 0.1)
        pattern3 = np.sin(np.linspace(0, 6 * np.pi, 30)) * 2.8 * np.sin(t * 0.3 + 1.5)
        three_people[:, t] += pattern1 + pattern2 + pattern3
        
    count = pipeline.count_occupancy(three_people)
    print(f"Result: {count} people counted.")
    assert count == 3, f"Failed Case 4: expected 3, got {count}"
    
    print("\n✅ All Occupancy Unit Tests Passed Successfully!")

if __name__ == "__main__":
    run_tests()
