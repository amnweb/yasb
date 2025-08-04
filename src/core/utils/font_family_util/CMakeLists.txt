set(CMAKE_POLICY_VERSION_MINIMUM 3.5) # for compatibility
cmake_minimum_required(VERSION 3.3)

project(font_font_family_util_proj)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/Release)
add_library(font_family_util SHARED
font_family_util.cpp 
font_family_util.hpp
logging.cpp
logging.hpp)

target_compile_features(font_family_util PUBLIC cxx_std_17)
target_link_libraries(font_family_util dwrite ole32 uuid gdi32)

include(GenerateExportHeader)
generate_export_header(font_family_util)
target_include_directories(font_family_util PUBLIC ${CMAKE_CURRENT_BINARY_DIR})
target_compile_definitions(font_family_util PRIVATE LOG_LEVEL=LOG_WARNING)
set_target_properties(font_family_util PROPERTIES PREFIX "")


if(MSVC)
	target_compile_options(font_family_util PRIVATE "/utf-8")
else()
	target_compile_options(font_family_util PRIVATE "-fexec-charset=utf-8")
endif()

set(MAKE_STANDALONE_DLL OFF)

if (MAKE_STANDALONE_DLL)
	if (MSVC)
		target_compile_options(font_family_util PRIVATE "/MT")
	else()
		message("The compiler is not msvc")
	endif()
endif()
