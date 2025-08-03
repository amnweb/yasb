#pragma once

#include <Windows.h>
#include <string>

namespace logging
{
	enum class LogLevel
	{
		LOG_DEBUG = 10,
		LOG_INFO = 20,
		LOG_WARNING = 30,
		LOG_ERROR = 40,
		LOG_CRITICAL = 50
	};

	class Logger
	{
	  public:
		LogLevel log_level;
		Logger(std::string name, LogLevel log_level = LogLevel::LOG_WARNING) noexcept;
		std::string name;

		void log_debug(const std::string &msg) const noexcept;
		void log_info(const std::string &msg) const noexcept;
		void log_warning(const std::string &msg) const noexcept;
		void log_error(const std::string &msg) const noexcept;
		void log_critical(const std::string &msg) const noexcept;
	};

	std::string get_last_win_error_msg() noexcept;
	std::string get_win_error_msg(HRESULT r) noexcept;

}; // namespace logging
