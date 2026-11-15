"""Portable supervisor entry. Both native backends retain ownership through cleanup."""
import os
from .platform import process_info
from .process_posix import group_members,stop_members

def main():
    if os.name=='nt':
        from .windows import worker_main
        return worker_main()
    from .process_posix import main as posix_main
    return posix_main()
if __name__=='__main__':raise SystemExit(main())
