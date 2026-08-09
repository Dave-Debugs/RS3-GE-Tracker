import hashlib
import sys
import os
import argparse

def compute_sha256(file_path):
    """Compute the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        print(f"Error computing hash: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Check the SHA-256 hash of a file (like RS3Tracker.exe) to verify its integrity.")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_exe = os.path.join(script_dir, "..", "backend", "dist", "RS3Tracker.exe")
    parser.add_argument("file", nargs="?", default=default_exe, help="Path to the file to check")
    parser.add_argument("--expected", "-e", help="Expected SHA-256 hash for verification")
    parser.add_argument("--save", "-s", action="store_true", help="Save the computed hash to a .sha256 file next to the original file")
    
    args = parser.parse_args()
    
    file_path = os.path.abspath(args.file)
    print(f"Target File: {file_path}")
    
    computed_hash = compute_sha256(file_path)
    if not computed_hash:
        sys.exit(1)
        
    print(f"\nSHA-256 Hash:\n{computed_hash}")
    
    if args.save:
        hash_file_path = f"{file_path}.sha256"
        try:
            with open(hash_file_path, "w") as f:
                f.write(f"{computed_hash} *{os.path.basename(file_path)}\n")
            print(f"\nHash saved to: {hash_file_path}")
        except Exception as e:
            print(f"Failed to save hash file: {e}")
            
    if args.expected:
        print("\nVerifying against expected hash...")
        if computed_hash.lower() == args.expected.lower():
            print("✅ SUCCESS: Hashes match! The file is intact and untampered.")
        else:
            print("❌ ERROR: Hashes DO NOT match! The file may be corrupted or tampered with.")
            print(f"Expected: {args.expected}")
            print(f"Got:      {computed_hash}")
            sys.exit(1)
            
if __name__ == "__main__":
    main()
