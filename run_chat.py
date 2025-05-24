import subprocess
import sys
import os

# Run the chatgpt.py script with stderr redirected to /dev/null
with open(os.devnull, 'w') as devnull:
    try:
        subprocess.run([sys.executable, 'chatgpt.py'], stderr=devnull)
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0) 