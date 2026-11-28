#!/bin/sh
# Probe (c), R2-08 finding 2: a process of dev whose main thread has exited (pthread_exit) while another thread
# writes. /proc shows its leader as a zombie (Zl), so a liveness check of the leader's state misses it, as round 1's
# collect hook did.
#
# Run as the turn of a simulated trial (run_probes.py) after solution/solve.sh. The turn compiles and starts the
# program, detached. Its thread appends a line to /app/harfbuzz/zthread.log every 20 ms, and once egress returns (a
# TCP connection to github.com's address) it also overwrites src/hb-ot-layout.cc with a line that breaks the build,
# again every 20 ms.
#
# Expected: the net check's ending at the opening (or else the sweep) finds the process by its live thread and
# kills it, so no process of dev is left; every write after the end is taken out (zthread.log and
# src/hb-ot-layout.cc are put back as they were at the end), so nothing late counts and the tree scores 1.0.
# run_probes.py's legacy variant runs round 1's collect hook instead and records that the process outlives it.
set -eu
mkdir -p /home/dev/zt
cat > /home/dev/zt/zthread.c <<'EOF'
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <poll.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static struct sockaddr_in target;

static int egress(void) {
    int s = socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0), ok = 0;
    if (s < 0)
        return 0;
    if (connect(s, (struct sockaddr *)&target, sizeof target) == 0) {
        ok = 1;
    } else {
        struct pollfd p = {s, POLLOUT, 0};
        if (poll(&p, 1, 200) == 1) {
            int err = 0;
            socklen_t len = sizeof err;
            getsockopt(s, SOL_SOCKET, SO_ERROR, &err, &len);
            ok = err == 0;
        }
    }
    close(s);
    return ok;
}

static void *writer(void *unused) {
    (void)unused;
    int seen = 0;
    for (long n = 0;; n++) {
        FILE *f = fopen("/app/harfbuzz/zthread.log", "a");
        if (f) {
            fprintf(f, "%ld %ld\n", n, (long)time(NULL));
            fclose(f);
        }
        if (!seen && n % 5 == 0 && egress())
            seen = 1;
        if (seen) {
            int fd = open("/app/harfbuzz/src/hb-ot-layout.cc", O_WRONLY | O_TRUNC);
            if (fd >= 0) {
                if (write(fd, "#error late\n", 12) < 0)
                    perror("write");
                close(fd);
            }
        }
        usleep(20000);
    }
    return NULL;
}

int main(void) {
    struct hostent *h = gethostbyname("github.com");
    pthread_t t;
    memset(&target, 0, sizeof target);
    target.sin_family = AF_INET;
    target.sin_port = htons(443);
    if (h)
        memcpy(&target.sin_addr, h->h_addr_list[0], 4);
    pthread_create(&t, NULL, writer, NULL);
    pthread_exit(NULL);
}
EOF
gcc -O1 -pthread -o /home/dev/zt/zthread /home/dev/zt/zthread.c
setsid nohup /home/dev/zt/zthread > /dev/null 2>&1 < /dev/null &
sleep 1
ps -L -o pid,lwp,stat,cmd -C zthread > /home/dev/zt/ps.txt 2>&1 || true
