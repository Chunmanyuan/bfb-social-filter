import cv2
import numpy as np

def ahash(image: np.ndarray, hash_size: int = 8) -> str:
    """
    Calculate the average hash (aHash) of an image.
    1. Resize to hash_size x hash_size.
    2. Convert to grayscale.
    3. Calculate the average pixel value.
    4. Compare pixels to the average to get a binary string.
    """
    if image is None:
        return ""
        
    # 1 & 2: Resize and convert to grayscale
    try:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    except Exception:
        return ""

    # 3: Calculate average
    avg = resized.mean()

    # 4: Compare to average
    diff = resized > avg
    
    # Convert boolean array to hex string
    # diff.flatten() gives a 1D array of booleans.
    # Pack them into a binary string '1100101...'
    hash_str = ''.join(['1' if val else '0' for val in diff.flatten()])
    return hash_str

def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Calculate the Hamming distance between two hash strings.
    A distance of 0 means identical hashes.
    """
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        # Return a large distance if hashes are invalid
        return 999 
    
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

def is_similar(img1: np.ndarray, img2: np.ndarray, threshold: int = 5) -> bool:
    """
    Check if two images are similar using aHash.
    threshold: maximum Hamming distance to be considered similar (default usually 5 for 64-bit hash)
    """
    h1 = ahash(img1)
    h2 = ahash(img2)
    return hamming_distance(h1, h2) <= threshold
