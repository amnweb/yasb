cmake_minimum_required(VERSION 3.15)
project(YASBTrayHook VERSION 1.0 LANGUAGES CXX)

# Set the C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# Detect architecture (supports both -A and toolchains)
if(CMAKE_GENERATOR_PLATFORM STREQUAL "ARM64" OR CMAKE_SYSTEM_PROCESSOR STREQUAL "ARM64")
    set(IS_ARM64 TRUE)
    set(ARCH_SUFFIX "_arm64")
else()
    set(IS_ARM64 FALSE)
    set(ARCH_SUFFIX "")
endif()

# Create the Shared Library (DLL)
add_library(YASBTrayHook SHARED trayhook.cpp version.rc)

# Set the output name with architecture suffix
set_target_properties(YASBTrayHook PROPERTIES OUTPUT_NAME "YASBTrayHook${ARCH_SUFFIX}")

if(MSVC)
    # Static CRT
    set_property(TARGET YASBTrayHook PROPERTY
        MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

    target_compile_options(YASBTrayHook PRIVATE
        /guard:cf       # Control Flow Guard
        /GS             # Buffer security checks
        /sdl            # Additional security checks
    )

    if(IS_ARM64)
        target_link_options(YASBTrayHook PRIVATE
            /guard:cf       # Control Flow Guard
            /DYNAMICBASE    # ASLR
            /NXCOMPAT       # DEP
            /CETCOMPAT:NO   # CET not supported on ARM64
        )
    else()
        target_link_options(YASBTrayHook PRIVATE
            /guard:cf       # Control Flow Guard
            /DYNAMICBASE    # ASLR
            /NXCOMPAT       # DEP
            /CETCOMPAT      # Intel CET shadow stack
        )
    endif()
endif()

# For version.rc to pick the correct filename
if(IS_ARM64)
    target_compile_definitions(YASBTrayHook PRIVATE BUILD_ARM64)
endif()

# Place the resulting DLL directly in the project root
set_target_properties(YASBTrayHook PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_SOURCE_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_SOURCE_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO "${CMAKE_SOURCE_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL "${CMAKE_SOURCE_DIR}"
    PDB_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
    PDB_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}"
    PDB_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}"
    PDB_OUTPUT_DIRECTORY_RELWITHDEBINFO "${CMAKE_BINARY_DIR}"
    PDB_OUTPUT_DIRECTORY_MINSIZEREL "${CMAKE_BINARY_DIR}"
)
