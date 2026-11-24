#pragma once

#include <atomic>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <limits>
#include <string>
#include <thread>

#include <fcntl.h>
#include <unistd.h>

namespace fenced_drive
{
/// Persist externally advertised generations away from the real-time loop.
class GenerationLedger
{
public:
  explicit GenerationLedger(std::filesystem::path path) : path_(std::move(path)) {}

  bool initialize()
  {
    const int fd = ::open(path_.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0 && errno != ENOENT) {
      return false;
    }
    if (fd >= 0) {
      char text[40];
      const auto count = ::read(fd, text, sizeof(text));
      ::close(fd);
      std::uint64_t value = 0;
      if (count < 2 || count == sizeof(text) || text[count - 1] != '\n') {
        return false;
      }
      const auto parsed = std::from_chars(text, text + count - 1, value);
      if (parsed.ec != std::errc{} || parsed.ptr != text + count - 1 || value == 0) {
        return false;
      }
      persisted_ = value;
      pending_ = value;
    }
    writer_ = std::jthread([this](std::stop_token stop) {
      using namespace std::chrono_literals;
      while (!stop.stop_requested()) {
        const auto next = pending_.load(std::memory_order_acquire);
        if (next > persisted_.load(std::memory_order_relaxed)) {
          if (!commit(next)) {
            failed_.store(true, std::memory_order_release);
            return;
          }
          persisted_.store(next, std::memory_order_release);
        }
        std::this_thread::sleep_for(2ms);
      }
    });
    return true;
  }

  std::uint64_t persisted() const noexcept
  {
    return persisted_.load(std::memory_order_acquire);
  }

  bool eligible(std::uint64_t generation) noexcept
  {
    if (failed_.load(std::memory_order_acquire) || generation == 0) {
      return false;
    }
    auto known = pending_.load(std::memory_order_acquire);
    while (known < generation &&
           !pending_.compare_exchange_weak(known, generation, std::memory_order_acq_rel)) {}
    return pending_.load(std::memory_order_acquire) == generation && persisted() == generation;
  }

private:
  bool commit(std::uint64_t next)
  {
    const auto folder = path_.parent_path();
    const int directory = ::open(folder.empty() ? "." : folder.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (directory < 0) {
      return false;
    }
    std::string temporary = path_.string() + ".XXXXXX";
    const int fd = ::mkstemp(temporary.data());
    if (fd < 0) {
      ::close(directory);
      return false;
    }
    const std::string text = std::to_string(next) + '\n';
    const bool written = ::write(fd, text.data(), text.size()) == static_cast<ssize_t>(text.size()) &&
      ::fsync(fd) == 0;
    const bool closed = ::close(fd) == 0;
    const bool published = written && closed && ::rename(temporary.c_str(), path_.c_str()) == 0;
    const bool durable = published && ::fsync(directory) == 0;
    if (!published) {
      ::unlink(temporary.c_str());
    }
    ::close(directory);
    return durable;
  }

  std::filesystem::path path_;
  std::atomic<std::uint64_t> persisted_{0}, pending_{0};
  std::atomic<bool> failed_{false};
  std::jthread writer_;
};
}
