#include "logging.hpp"

#include <Windows.h>
#include <dwrite.h>
#include <iostream>
#include <string>

namespace logging
{
	Logger::Logger(std::string name, const LogLevel log_level) noexcept : log_level(log_level), name(std::move(name))
	{
	}

	void Logger::log_debug(const std::string& msg) const noexcept
	{
		if (log_level <= LogLevel::LOG_DEBUG)
		{
			std::cerr << "DEBUG:" <<  name << ":" << msg << std::endl;
		}
	}

	void Logger::log_info(const std::string& msg) const noexcept
	{
		if (log_level <= LogLevel::LOG_INFO)
		{
			std::cerr << "INFO:" <<  name << ":" << msg << std::endl;
		}
	}

	void Logger::log_warning(const std::string& msg) const noexcept
	{
		if (log_level <= LogLevel::LOG_WARNING)
		{
			std::cerr << "WARNING:" <<  name << ":" << msg << std::endl;
		}
	}

	void Logger::log_error(const std::string& msg) const noexcept
	{
		if (log_level <= LogLevel::LOG_ERROR)
		{
			std::cerr << "ERROR:" <<  name << ":" << msg << std::endl;
		}
	}

	void Logger::log_critical(const std::string& msg) const noexcept
	{
		if (log_level <= LogLevel::LOG_CRITICAL)
		{
			std::cerr << "CRITICAL:" <<  name << ":" << msg << std::endl;
		}
	}

	std::string get_win_error_msg(const HRESULT r) noexcept
	{
		LPSTR msgBuffer = nullptr;

		DWORD size = FormatMessage(
			FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
			nullptr,
			r,
			MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
			reinterpret_cast<LPTSTR>(&msgBuffer),
			0,
			nullptr);

		if (!size)
		{
			Logger logger(__FUNCTION__);
			logger.log_error("FormatMessage failed with : " + std::to_string(GetLastError()));

			return "";
		}

		std::string msg = msgBuffer;

		LocalFree(msgBuffer);

		return msg;
	}

	std::string get_last_win_error_msg() noexcept
	{
		return get_win_error_msg(static_cast<HRESULT>(GetLastError()));
	}
};
