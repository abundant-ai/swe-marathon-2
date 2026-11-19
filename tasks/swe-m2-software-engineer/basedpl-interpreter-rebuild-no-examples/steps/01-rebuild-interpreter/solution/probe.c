/* A record of how a trial's sandbox treats the released interpreter's set-group-id exec, for the
   task's authors. It is not part of the solution and nothing in it changes the solution's result:
   solve.sh builds it with gcc once the solution is installed, runs it as the agent's user and
   copies what it prints to /logs/agent/probe.txt. It reads no byte of the interpreter; it records
   only whether each way of reading one would have worked.

   For a plain exec of /opt/bpl/bpl and for one after PTRACE_TRACEME it records the
   interpreter's real and effective ids, AT_SECURE, whether an LD_PRELOAD library's constructor runs
   inside it, and whether PTRACE_PEEKDATA and /proc/<pid>/mem reads of it succeed; and the kernel,
   with whether it is gVisor's.

   Built twice: plainly, the probe; with -DPRELOAD -shared -fPIC, the preloaded library.
   usage: probe <preload.so> */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/auxv.h>
#include <sys/ptrace.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifdef PRELOAD

/* Runs only where the loader honours LD_PRELOAD in the compiler's process: says so, and how. */
__attribute__((constructor)) static void probe_constructor(void) {
    const char *out = getenv("BPL_PROBE_OUT");
    if (!out) return;
    FILE *f = fopen(out, "w");
    if (!f) return;
    fprintf(f, "the constructor ran inside the compiler: AT_SECURE=%lu egid=%d gid=%d\n",
            getauxval(AT_SECURE), (int)getegid(), (int)getgid());
    fclose(f);
}

#else

static const char *BPL = "/opt/bpl/bpl";

static void first_line(const char *label, const char *path) {
    char line[512];
    FILE *f = fopen(path, "r");
    if (!f) {
        printf("%s: unreadable (%s)\n", label, strerror(errno));
        return;
    }
    if (fgets(line, sizeof line, f)) printf("%s: %s%s", label, line, strchr(line, '\n') ? "" : "\n");
    fclose(f);
}

static void ids(pid_t pid) {
    char path[64], line[256];
    snprintf(path, sizeof path, "/proc/%d/status", (int)pid);
    FILE *f = fopen(path, "r");
    if (!f) {
        printf("  status: unreadable (%s)\n", strerror(errno));
        return;
    }
    while (fgets(line, sizeof line, f))
        if (!strncmp(line, "Name:", 5) || !strncmp(line, "Uid:", 4) || !strncmp(line, "Gid:", 4) ||
            !strncmp(line, "TracerPid:", 10))
            printf("  status %s", line);
    fclose(f);
}

/* Prints AT_SECURE from /proc/<pid>/auxv and returns AT_ENTRY, or 0 where it is unreadable. */
static unsigned long secure_and_entry(pid_t pid) {
    char path[64];
    unsigned long pair[2], entry = 0;
    long secure = -1;
    snprintf(path, sizeof path, "/proc/%d/auxv", (int)pid);
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        printf("  auxv: unreadable (%s)\n", strerror(errno));
        return 0;
    }
    while (read(fd, pair, sizeof pair) == (ssize_t)sizeof pair && pair[0] != AT_NULL) {
        if (pair[0] == AT_SECURE) secure = (long)pair[1];
        if (pair[0] == AT_ENTRY) entry = pair[1];
    }
    close(fd);
    printf("  auxv: AT_SECURE=%ld\n", secure);
    return entry;
}

/* Whether one word at `addr` could be read, by ptrace (only for a traced child) and through
   /proc/<pid>/mem. Nothing read is kept or printed. */
static void reads(pid_t pid, unsigned long addr, int traced) {
    if (!addr) {
        printf("  reads: no address to try (auxv unreadable)\n");
        return;
    }
    if (traced) {
        errno = 0;
        long word = ptrace(PTRACE_PEEKDATA, pid, (void *)addr, NULL);
        (void)word;
        printf("  PTRACE_PEEKDATA at the entry point: %s\n", errno ? strerror(errno) : "succeeded");
    }
    char path[64];
    unsigned char byte;
    snprintf(path, sizeof path, "/proc/%d/mem", (int)pid);
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        printf("  /proc/<pid>/mem: cannot open (%s)\n", strerror(errno));
        return;
    }
    ssize_t got = pread(fd, &byte, 1, (off_t)addr);
    printf("  /proc/<pid>/mem read at the entry point: %s\n", got == 1 ? "succeeded" : strerror(errno));
    close(fd);
}

static void finish(pid_t pid, int traced) {
    int status;
    kill(pid, SIGKILL);
    for (int i = 0; i < 20 && waitpid(pid, &status, 0) == pid; i++) {
        if (WIFEXITED(status) || WIFSIGNALED(status)) return;
        if (traced) ptrace(PTRACE_CONT, pid, NULL, NULL);
    }
}

static void exec_once(const char *preload, const char *dir, int traced) {
    char out[600], env_preload[700], env_out[700];
    snprintf(out, sizeof out, "%s/constructor-%s.txt", dir, traced ? "traced" : "plain");
    snprintf(env_preload, sizeof env_preload, "LD_PRELOAD=%s", preload);
    snprintf(env_out, sizeof env_out, "BPL_PROBE_OUT=%s", out);
    unlink(out);
    printf("%s exec of %s:\n", traced ? "after PTRACE_TRACEME, the" : "a plain", BPL);
    int input[2];
    if (pipe(input) != 0) {
        printf("  pipe: %s\n", strerror(errno));
        return;
    }
    fflush(stdout);
    pid_t pid = fork();
    if (pid < 0) {
        printf("  fork: %s\n", strerror(errno));
        return;
    }
    if (pid == 0) {
        /* bpl -e '•nget "-"' waits on its standard input, which stays open until the probe is done. */
        dup2(input[0], 0);
        close(input[0]);
        close(input[1]);
        int null = open("/dev/null", O_WRONLY);
        if (null >= 0) {
            dup2(null, 1);
            dup2(null, 2);
        }
        if (traced && ptrace(PTRACE_TRACEME, 0, NULL, NULL) != 0) _exit(120);
        char *argv[] = { "bpl", "-e", "•nget \"-\"", NULL };
        char *envp[] = { env_preload, env_out, "PATH=/usr/bin:/bin", "HOME=/tmp", NULL };
        execve(BPL, argv, envp);
        _exit(121);
    }
    close(input[0]);
    if (traced) {
        int status = 0;
        if (waitpid(pid, &status, 0) != pid || !WIFSTOPPED(status)) {
            printf("  no stop at the exec (wait status %#x)\n", (unsigned)status);
            close(input[1]);
            finish(pid, traced);
            return;
        }
        printf("  stopped at the exec, before the loader ran:\n");
        ids(pid);
        reads(pid, secure_and_entry(pid), traced);
        ptrace(PTRACE_CONT, pid, NULL, NULL);
    }
    struct timespec pause = { 0, 400 * 1000 * 1000 };   /* bpl reaches the read */
    nanosleep(&pause, NULL);
    printf("  running:\n");
    ids(pid);
    unsigned long entry = secure_and_entry(pid);
    if (!traced) reads(pid, entry, traced);
    FILE *f = fopen(out, "r");
    char line[256];
    if (f && fgets(line, sizeof line, f)) printf("  LD_PRELOAD: %s", line);
    else printf("  LD_PRELOAD: the constructor did not run\n");
    if (f) fclose(f);
    close(input[1]);
    finish(pid, traced);
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: probe <preload.so>\n");
        return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    struct utsname u;
    if (uname(&u) == 0) printf("kernel: %s %s %s %s\n", u.sysname, u.release, u.version, u.machine);
    first_line("/proc/version", "/proc/version");
    char version[512] = "";
    FILE *v = fopen("/proc/version", "r");
    if (v) {
        if (!fgets(version, sizeof version, v)) version[0] = 0;
        fclose(v);
    }
    /* gVisor reports a fixed Linux 4.4.0 built "Sun Jan 10 15:06:54 PST 2016". */
    printf("gVisor: %s\n", strstr(version, "4.4.0") && strstr(version, "Jan 10 15:06:54 PST 2016") ? "yes" : "not by its version");
    printf("probe: uid %d gid %d euid %d egid %d\n", (int)getuid(), (int)getgid(), (int)geteuid(), (int)getegid());
    struct stat st;
    if (stat(BPL, &st) == 0)
        printf("%s: mode %o owner %d group %d\n", BPL, (unsigned)st.st_mode & 07777, (int)st.st_uid, (int)st.st_gid);
    else
        printf("%s: %s\n", BPL, strerror(errno));
    char dir[] = "/tmp/bpl-probe-XXXXXX";
    if (!mkdtemp(dir)) {
        printf("mkdtemp: %s\n", strerror(errno));
        return 0;
    }
    chmod(dir, 0755);
    exec_once(argv[1], dir, 0);
    exec_once(argv[1], dir, 1);
    char path[700];
    for (int traced = 0; traced < 2; traced++) {
        snprintf(path, sizeof path, "%s/constructor-%s.txt", dir, traced ? "traced" : "plain");
        unlink(path);
    }
    rmdir(dir);
    return 0;
}

#endif
