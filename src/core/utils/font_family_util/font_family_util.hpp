#pragma once

#include "font_family_util_export.h"

namespace font_family_util
{
	extern "C"
	{
		FONT_FAMILY_UTIL_EXPORT bool init();
		FONT_FAMILY_UTIL_EXPORT void cleanup();
		FONT_FAMILY_UTIL_EXPORT const char *
		get_gdi_family_from_directwrite(const char *direct_write_family);
		FONT_FAMILY_UTIL_EXPORT const char *get_directwrite_family_from_gdi(const char *gdi_family);
	}
} // namespace font_family_util