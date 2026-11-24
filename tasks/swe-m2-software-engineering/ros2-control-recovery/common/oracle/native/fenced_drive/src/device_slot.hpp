#pragma once

#include <array>
#include <bit>
#include <cstdint>
#include <fcntl.h>
#include <optional>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <system_error>
#include <time.h>
#include <unistd.h>

namespace fenced_drive
{
using Record = std::array<std::uint64_t, 8>;

/// Fixed shared-memory transport with one writer and versioned coherent snapshots.
class Slot
{
public:
  Slot() = default;
  Slot(const Slot &) = delete;
  Slot & operator=(const Slot &) = delete;

  ~Slot()
  {
    if (words_ != nullptr) {
      munmap(words_, sizeof(Record));
    }
  }

  /// Map an existing device endpoint during configuration, outside the update cycle.
  void map(const std::string & name, bool writer)
  {
    const int fd = open(name.c_str(), O_CLOEXEC | (writer ? O_RDWR : O_RDONLY));
    if (fd < 0) {
      throw std::system_error(errno, std::generic_category(), "open device slot");
    }
    struct stat metadata {};
    if (fstat(fd, &metadata) != 0 || !S_ISREG(metadata.st_mode) || metadata.st_size != sizeof(Record)) {
      close(fd);
      throw std::runtime_error("Device slot must be one existing 64-byte regular file");
    }
    void * linked = mmap(nullptr, sizeof(Record), PROT_READ | (writer ? PROT_WRITE : 0), MAP_SHARED, fd, 0);
    const int failure = errno;
    close(fd);
    if (linked == MAP_FAILED) {
      throw std::system_error(failure, std::generic_category(), "map device slot");
    }
    if (words_ != nullptr) {
      munmap(words_, sizeof(Record));
    }
    words_ = static_cast<std::uint64_t *>(linked);
  }

  /// Copy a coherent published record, returning no snapshot for a torn read.
  std::optional<Record> read() const noexcept
  {
    if (words_ == nullptr) {
      return std::nullopt;
    }
    const auto first = __atomic_load_n(words_, __ATOMIC_ACQUIRE);
    if (first == 0 || (first & 1U) != 0) {
      return std::nullopt;
    }
    Record out{};
    out[0] = first;
    for (std::size_t i = 1; i < out.size(); ++i) {
      out[i] = __atomic_load_n(words_ + i, __ATOMIC_RELAXED);
    }
    __atomic_thread_fence(__ATOMIC_ACQUIRE);
    if (__atomic_load_n(words_, __ATOMIC_ACQUIRE) != first) {
      return std::nullopt;
    }
    return out;
  }

  /// Publish the payload and sequence in order without calling the filesystem.
  void publish(const Record & record) noexcept
  {
    if (words_ == nullptr) {
      return;
    }
    const auto observed = __atomic_load_n(words_, __ATOMIC_RELAXED);
    const auto odd = (observed | 1U);
    __atomic_store_n(words_, odd, __ATOMIC_SEQ_CST);
    for (std::size_t i = 1; i < record.size(); ++i) {
      __atomic_store_n(words_ + i, record[i], __ATOMIC_RELAXED);
    }
    __atomic_store_n(words_, odd + 1U, __ATOMIC_RELEASE);
  }

private:
  std::uint64_t * words_ = nullptr;
};

/// Read the monotonic kernel clock used by the device capture timestamps.
inline std::uint64_t monotonic_ns() noexcept
{
  timespec now{};
  clock_gettime(CLOCK_MONOTONIC, &now);
  return static_cast<std::uint64_t>(now.tv_sec) * 1000000000ULL + static_cast<std::uint64_t>(now.tv_nsec);
}
}
