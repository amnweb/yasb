#define UNICODE
#define _UNICODE

#define _CRT_SECURE_NO_WARNINGS

#include "font_family_util.hpp"

#include <Windows.h>
#include <codecvt>
#include <cstring>
#include <dwrite.h>
#include <optional>
#include <string>
#include <unordered_map>
#include <locale>

#include "logging.hpp"

constexpr auto logger_log_level = logging::LogLevel::LOG_LEVEL;

namespace
{
	logging::Logger logger("font_family_util", logger_log_level);

	std::unordered_map<std::string, std::string> gdi_to_directwrite;
	std::unordered_map<std::string, std::string> directwrite_to_gdi;

	std::optional<std::string>
	get_family_name_of_cur_locale(IDWriteFontFamily* font_family) noexcept;
	std::optional<std::pair<std::string, std::string>> get_gdi_and_directwrite_family_name(
		IDWriteFactory* factory, IDWriteFontFamily* font_family) noexcept;

	std::optional<std::string>
	get_family_name_of_cur_locale(IDWriteFontFamily* font_family) noexcept
	{
		wchar_t locale_name[LOCALE_NAME_MAX_LENGTH];

		if (!GetUserDefaultLocaleName(locale_name, LOCALE_NAME_MAX_LENGTH))
		{
			logger.log_warning("Failed to get the default locale. "
				"Defaulting to en_us");
			std::wcscpy(locale_name, L"en_us");
		}

		IDWriteLocalizedStrings* family_names;
		HRESULT hr = font_family->GetFamilyNames(&family_names);

		if (FAILED(hr))
		{
			logger.log_error("Getting family names failed" +
				std::string(logging::get_win_error_msg(hr)));
			return std::nullopt;
		}

		UINT32 family_name_index = 0;
		[[maybe_unused]] BOOL is_exist;
		hr = family_names->FindLocaleName(locale_name, &family_name_index, &is_exist);

		if (FAILED(hr))
		{
			logger.log_error("Getting a family name of the current locale "
				"failed : " +
				std::string(logging::get_win_error_msg(hr)));
			return std::nullopt;
		}

		UINT32 family_name_len;

		hr = family_names->GetStringLength(family_name_index, &family_name_len);

		if (FAILED(hr))
		{
			logger.log_error("Getting the length of the family name failed : " +
				std::string(logging::get_win_error_msg(hr)));
			return std::nullopt;
		}

		wchar_t* family_name = nullptr;

		try
		{
			family_name = new wchar_t[family_name_len + 1];
		}
		catch (std::exception& e)
		{
			logger.log_error("Heap allocation failed : " + std::string(e.what()));
			return std::nullopt;
		}

		hr = family_names->GetString(family_name_index, family_name, family_name_len + 1);

		if (FAILED(hr))
		{
			logger.log_error("Getting the string of the family name(object) "
				"failed : " +
				std::string(logging::get_win_error_msg(hr)));

			delete[] family_name;
			return std::nullopt;
		}

		std::wstring_convert<std::codecvt_utf8_utf16<wchar_t>> converter;
		auto result = converter.to_bytes(family_name);
		delete[] family_name;

		return result;
	}

	std::optional<std::pair<std::string, std::string>> get_gdi_and_directwrite_family_name(
		IDWriteFactory* const factory, IDWriteFontFamily* const font_family) noexcept
	{
		std::optional<std::string> get_family_name_of_cur_locale_result =
			get_family_name_of_cur_locale(font_family);

		if (!get_family_name_of_cur_locale_result.has_value())
		{
			logger.log_error("get_family_name_of_"
				"cur_locale() failed");
			return std::nullopt;
		}

		std::string directwrite_family_name =
			std::move(get_family_name_of_cur_locale_result.value());
		IDWriteFont* dwrite_font = nullptr;
		HRESULT hr = font_family->GetFirstMatchingFont(DWRITE_FONT_WEIGHT_NORMAL,
														DWRITE_FONT_STRETCH_NORMAL,
														DWRITE_FONT_STYLE_NORMAL, &dwrite_font);

		if (FAILED(hr))
		{
			logger.log_error("GetFirstMatchingFont() failed : " +
				logging::get_win_error_msg(hr));
			return std::nullopt;
		}

		IDWriteGdiInterop* interop = nullptr;
		hr = factory->GetGdiInterop(&interop);

		if (FAILED(hr))
		{
			logger.log_error("GetGdiInterop() failed : " + logging::get_win_error_msg(hr));
			return std::nullopt;
		}

		LOGFONTW lf{};
		BOOL is_system_font{};

		hr = interop->ConvertFontToLOGFONT(dwrite_font, &lf, &is_system_font);

		if (FAILED(hr))
		{
			logger.log_error("ConvertFontToLOGFONT() failed : " +
				logging::get_win_error_msg(hr));
			return std::nullopt;
		}

		std::string gdi_family_name;

		try
		{
			std::wstring_convert<std::codecvt_utf8_utf16<wchar_t>> converter;
			gdi_family_name = converter.to_bytes(lf.lfFaceName);
		}
		catch (std::exception& e)
		{
			logger.log_error("Encoding converter failed : " + std::string(e.what()));
			return std::nullopt;
		}

		return std::make_pair(gdi_family_name, directwrite_family_name);
	}
} // namespace

namespace font_family_util
{
	extern "C" {
	// Returns true if succeeded, otherwise false
	bool init() // Probably compatible with c _Bool I guess?
	{
		IDWriteFactory* factory = nullptr;
		HRESULT hr = DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, __uuidof(IDWriteFactory),
								reinterpret_cast<IUnknown**>(&factory));

		if (FAILED(hr))
		{
			logger.log_error("Failed to create a DWrite factory : " +
				logging::get_win_error_msg(hr));
			return false;
		}

		IDWriteFontCollection* font_collection = nullptr;
		hr = factory->GetSystemFontCollection(&font_collection);

		if (FAILED(hr))
		{
			logger.log_error("GetSystemFontCollection() failed : " +
				logging::get_win_error_msg(hr));
			return false;
		}

		int family_count = static_cast<int>(font_collection->GetFontFamilyCount());

		for (int i = 0; i < family_count; i++)
		{
			IDWriteFontFamily* font_family = nullptr;
			hr = font_collection->GetFontFamily(static_cast<UINT32>(i), &font_family);

			if (FAILED(hr))
			{
				logger.log_error("GetFontFamily() failed : " + logging::get_win_error_msg(hr));
				continue;
			}

			std::optional<std::pair<std::string, std::string>> get_names_result = get_gdi_and_directwrite_family_name(
				factory, font_family);

			if (!get_names_result.has_value())
			{
				logger.log_warning(
					"Getting gdi and directwrite family name failed for IDWriteFontFamily : " + std::to_string(
						reinterpret_cast<unsigned long long>(font_family)));
				continue;
			}

			auto [gdi_family_name, directwrite_family_name] = std::move(get_names_result.value());

			gdi_to_directwrite[gdi_family_name] = directwrite_family_name;
			directwrite_to_gdi[directwrite_family_name] = gdi_family_name;

			logger.log_debug(std::string(gdi_family_name) +
				"(gdi) : " + directwrite_family_name + "(directwrite)");
		}

		return true;
	}

	void cleanup()
	{
	}
	}

	const char* get_gdi_family_from_directwrite(const char* const direct_write_family)
	{
		try
		{
			return directwrite_to_gdi.at(direct_write_family).c_str();
		}
		catch ([[maybe_unused]] std::out_of_range& e)
		{
			return nullptr;
		}
		catch (std::exception& e)
		{
			logger.log_error("an unknown exception occured in " + std::string(__FUNCTION__) +
				" : " + e.what());
		}

		return nullptr;
	}

	const char* get_directwrite_family_from_gdi(const char* const gdi_family)
	{
		try
		{
			return gdi_to_directwrite.at(gdi_family).c_str();
		}
		catch ([[maybe_unused]] std::out_of_range& e)
		{
			return nullptr;
		}
		catch (std::exception& e)
		{
			logger.log_error("an unknown exception occured in " + std::string(__FUNCTION__) +
				" : " + e.what());
		}

		return nullptr;
	}
} // namespace font_family_util
