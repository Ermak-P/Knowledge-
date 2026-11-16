"""Linux kernel-enforced connect denial inherited by installer and pip children."""
import ctypes as c,ctypes.util,errno,os,socket,sys
require=lambda value: value or (_ for _ in ()).throw(RuntimeError('offline network isolation unavailable'))
require(sys.platform=='linux');lib=c.CDLL(ctypes.util.find_library('seccomp'),use_errno=True)
lib.seccomp_init.argtypes=[c.c_uint32];lib.seccomp_init.restype=c.c_void_p
lib.seccomp_syscall_resolve_name.argtypes=[c.c_char_p];lib.seccomp_syscall_resolve_name.restype=c.c_int
lib.seccomp_rule_add.argtypes=[c.c_void_p,c.c_uint32,c.c_int,c.c_uint];lib.seccomp_rule_add.restype=c.c_int
lib.seccomp_load.argtypes=[c.c_void_p];lib.seccomp_load.restype=c.c_int
context=lib.seccomp_init(0x7fff0000);require(context)
require(lib.seccomp_rule_add(context,0x00050000|errno.ENETUNREACH,lib.seccomp_syscall_resolve_name(b'connect'),0)==0)
require(lib.seccomp_load(context)==0)
try:socket.create_connection(('127.0.0.1',9),timeout=1);raise RuntimeError('network guard failed')
except OSError as error:require(error.errno==errno.ENETUNREACH)
print('OFFLINE: kernel connect denial verified; inherited across exec/subprocess.',flush=True)
os.execv(sys.executable,[sys.executable,*sys.argv[1:]])
