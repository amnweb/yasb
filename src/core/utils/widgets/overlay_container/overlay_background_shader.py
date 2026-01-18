"""
Shader Background Handler for Overlay Container Widget
Supports preset and custom GLSL shaders as animated backgrounds.
"""

import logging
import os
import time
import struct
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect

# OpenGL is optional - if not installed, shader features won't be available
try:
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader, QOpenGLBuffer, QOpenGLVertexArrayObject
    from OpenGL import GL
    OPENGL_AVAILABLE = True
except ImportError as e:
    OPENGL_AVAILABLE = False
    QOpenGLWidget = QWidget  # Fallback to regular QWidget
    logging.warning(f"OpenGL not available ({e}). Shader backgrounds will not be available. Install with: pip install PyOpenGL PyOpenGL_accelerate")


# Preset shader sources
PRESET_SHADERS = {}

# Default vertex shader (used for all presets)
DEFAULT_VERTEX_SHADER = """
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec2 aTexCoord;

out vec2 TexCoord;

void main()
{
    gl_Position = vec4(aPos, 1.0);
    TexCoord = aTexCoord;
}
"""

# Plasma shader
PRESET_SHADERS["plasma"] = """
#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform float time;
uniform float speed;
uniform float scale;
uniform vec2 resolution;
uniform vec3 colors[3];
uniform int numColors;

void main()
{
    vec2 uv = TexCoord * scale;
    float t = time * speed;

    float v1 = sin(uv.x * 10.0 + t);
    float v2 = sin(10.0 * (uv.x * sin(t / 2.0) + uv.y * cos(t / 3.0)) + t);
    float v3 = sin(sqrt(100.0 * (uv.x * uv.x + uv.y * uv.y) + 1.0) + t);
    float v = v1 + v2 + v3;

    vec3 color;
    if (numColors >= 3) {
        float t = (sin(v * 0.5) + 1.0) / 2.0;
        color = mix(colors[0], mix(colors[1], colors[2], t), t);
    } else {
        color = vec3(sin(v), sin(v + 2.0), sin(v + 4.0)) * 0.5 + 0.5;
    }

    FragColor = vec4(color, 1.0);
}
"""

# Wave shader
PRESET_SHADERS["wave"] = """
#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform float time;
uniform float speed;
uniform float scale;
uniform vec2 resolution;
uniform vec3 colors[3];
uniform int numColors;

void main()
{
    vec2 uv = TexCoord * scale;
    float t = time * speed;

    float wave = sin(uv.x * 5.0 + t) * cos(uv.y * 5.0 + t * 0.5) * 0.5 + 0.5;

    vec3 color;
    if (numColors >= 2) {
        color = mix(colors[0], colors[1], wave);
    } else {
        color = vec3(wave, wave * 0.8, wave * 1.2);
    }

    FragColor = vec4(color, 1.0);
}
"""

# Ripple shader
PRESET_SHADERS["ripple"] = """
#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform float time;
uniform float speed;
uniform float scale;
uniform vec2 resolution;
uniform vec3 colors[3];
uniform int numColors;

void main()
{
    vec2 uv = (TexCoord - 0.5) * 2.0 * scale;
    float t = time * speed;

    float dist = length(uv);
    float ripple = sin(dist * 10.0 - t * 5.0) * 0.5 + 0.5;
    ripple *= 1.0 - smoothstep(0.0, 2.0, dist);

    vec3 color;
    if (numColors >= 2) {
        color = mix(colors[0], colors[1], ripple);
    } else {
        color = vec3(0.2, 0.5, 1.0) * ripple;
    }

    FragColor = vec4(color, 1.0);
}
"""

# Tunnel shader
PRESET_SHADERS["tunnel"] = """
#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform float time;
uniform float speed;
uniform float scale;
uniform vec2 resolution;
uniform vec3 colors[3];
uniform int numColors;

void main()
{
    vec2 uv = (TexCoord - 0.5) * 2.0;
    float t = time * speed;

    float angle = atan(uv.y, uv.x);
    float radius = length(uv);

    float tunnel = mod(1.0 / radius + t, 1.0);
    float spiral = mod(angle * 2.0 + t, 6.28) / 6.28;

    vec3 color;
    if (numColors >= 2) {
        color = mix(colors[0], colors[1], tunnel * spiral);
    } else {
        color = vec3(tunnel, spiral, tunnel * spiral);
    }

    FragColor = vec4(color, 1.0);
}
"""

# Mandelbrot shader
PRESET_SHADERS["mandelbrot"] = """
#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform float time;
uniform float speed;
uniform float scale;
uniform vec2 resolution;
uniform vec3 colors[3];
uniform int numColors;

void main()
{
    vec2 c = (TexCoord - 0.5) * 3.0 * scale;
    c.x += sin(time * speed * 0.2) * 0.5;
    c.y += cos(time * speed * 0.15) * 0.5;

    vec2 z = vec2(0.0);
    float iterations = 0.0;
    const float maxIterations = 50.0;

    for (float i = 0.0; i < maxIterations; i++) {
        z = vec2(z.x * z.x - z.y * z.y, 2.0 * z.x * z.y) + c;
        if (length(z) > 2.0) break;
        iterations++;
    }

    float t = iterations / maxIterations;

    vec3 color;
    if (numColors >= 3) {
        color = mix(colors[0], mix(colors[1], colors[2], t), t);
    } else {
        color = vec3(t, t * t, sqrt(t));
    }

    FragColor = vec4(color, 1.0);
}
"""

# Noise shader
PRESET_SHADERS["noise"] = """
#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform float time;
uniform float speed;
uniform float scale;
uniform vec2 resolution;
uniform vec3 colors[3];
uniform int numColors;

float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
}

float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

void main()
{
    vec2 uv = TexCoord * scale;
    float t = time * speed;

    float n = noise(uv * 5.0 + t);
    n += 0.5 * noise(uv * 10.0 + t * 1.5);
    n += 0.25 * noise(uv * 20.0 + t * 2.0);
    n /= 1.75;

    vec3 color;
    if (numColors >= 2) {
        color = mix(colors[0], colors[1], n);
    } else {
        color = vec3(n);
    }

    FragColor = vec4(color, 1.0);
}
"""

# Gradient shader
PRESET_SHADERS["gradient"] = """
#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform float time;
uniform float speed;
uniform float scale;
uniform vec2 resolution;
uniform vec3 colors[3];
uniform int numColors;

void main()
{
    float t = mod(time * speed * 0.2, 1.0);
    vec2 uv = TexCoord;

    vec3 color;
    if (numColors >= 3) {
        float pos = (uv.x + uv.y) * 0.5 + t;
        pos = fract(pos);
        if (pos < 0.5) {
            color = mix(colors[0], colors[1], pos * 2.0);
        } else {
            color = mix(colors[1], colors[2], (pos - 0.5) * 2.0);
        }
    } else if (numColors >= 2) {
        color = mix(colors[0], colors[1], uv.x);
    } else {
        color = vec3(uv.x, uv.y, 1.0 - uv.x);
    }

    FragColor = vec4(color, 1.0);
}
"""


class ShaderWidget(QOpenGLWidget):
    """OpenGL widget for rendering shaders."""

    def __init__(self, parent, shader_config):
        super().__init__(parent)
        self.config = shader_config
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self.start_time = time.time()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)  # ~60 FPS

        # Parse colors
        self.colors = self._parse_colors(shader_config.get("colors", []))

        # Set background to transparent
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _parse_colors(self, color_strings):
        """Parse color strings to RGB tuples."""
        colors = []
        for color_str in color_strings:
            color = QColor(color_str)
            if color.isValid():
                colors.append((color.redF(), color.greenF(), color.blueF()))

        # Default colors if none specified
        if not colors:
            colors = [
                (0.0, 1.0, 1.0),  # Cyan
                (1.0, 0.0, 1.0),  # Magenta
                (1.0, 1.0, 0.0),  # Yellow
            ]

        return colors

    def initializeGL(self):
        """Initialize OpenGL resources."""
        try:
            # Create shader program
            self.shader_program = QOpenGLShaderProgram(self)

            # Load shaders
            preset = self.config.get("preset", "plasma")
            if preset == "custom":
                vertex_file = self.config.get("custom_vertex_file", "")
                fragment_file = self.config.get("custom_fragment_file", "")

                if vertex_file and os.path.exists(vertex_file):
                    with open(vertex_file, 'r') as f:
                        vertex_source = f.read()
                else:
                    vertex_source = DEFAULT_VERTEX_SHADER

                if fragment_file and os.path.exists(fragment_file):
                    with open(fragment_file, 'r') as f:
                        fragment_source = f.read()
                else:
                    logging.error("ShaderWidget: Custom fragment shader file not found")
                    fragment_source = PRESET_SHADERS["plasma"]
            else:
                vertex_source = DEFAULT_VERTEX_SHADER
                fragment_source = PRESET_SHADERS.get(preset, PRESET_SHADERS["plasma"])

            # Compile shaders
            if not self.shader_program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, vertex_source):
                logging.error(f"ShaderWidget: Failed to compile vertex shader: {self.shader_program.log()}")
                return

            if not self.shader_program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, fragment_source):
                logging.error(f"ShaderWidget: Failed to compile fragment shader: {self.shader_program.log()}")
                return

            if not self.shader_program.link():
                logging.error(f"ShaderWidget: Failed to link shader program: {self.shader_program.log()}")
                return

            # Create fullscreen quad vertices (2 triangles)
            # Format: x, y, z, u, v (position + texture coordinates)
            vertices = [
                # First triangle (bottom-left, bottom-right, top-left)
                -1.0, -1.0, 0.0,  0.0, 0.0,  # Bottom-left
                 1.0, -1.0, 0.0,  1.0, 0.0,  # Bottom-right
                -1.0,  1.0, 0.0,  0.0, 1.0,  # Top-left
                # Second triangle (bottom-right, top-right, top-left)
                 1.0, -1.0, 0.0,  1.0, 0.0,  # Bottom-right
                 1.0,  1.0, 0.0,  1.0, 1.0,  # Top-right
                -1.0,  1.0, 0.0,  0.0, 1.0,  # Top-left
            ]

            # Convert to bytes
            vertex_data = struct.pack(f'{len(vertices)}f', *vertices)

            # Create VAO
            self.vao = QOpenGLVertexArrayObject()
            if not self.vao.create():
                logging.error("ShaderWidget: Failed to create VAO")
                return
            self.vao.bind()

            # Create VBO
            self.vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            if not self.vbo.create():
                logging.error("ShaderWidget: Failed to create VBO")
                return
            self.vbo.bind()
            self.vbo.allocate(vertex_data, len(vertex_data))

            # Set vertex attribute pointers
            self.shader_program.bind()

            # Position attribute (location 0)
            self.shader_program.enableAttributeArray(0)
            self.shader_program.setAttributeBuffer(0, GL.GL_FLOAT, 0, 3, 5 * 4)  # 3 floats, stride 5*4 bytes

            # Texture coordinate attribute (location 1)
            self.shader_program.enableAttributeArray(1)
            self.shader_program.setAttributeBuffer(1, GL.GL_FLOAT, 3 * 4, 2, 5 * 4)  # 2 floats, offset 3*4 bytes

            # Unbind
            self.vao.release()
            self.vbo.release()
            self.shader_program.release()

            logging.info(f"ShaderWidget: Initialized {preset} shader with vertex buffers")

        except Exception as e:
            logging.error(f"ShaderWidget: Error initializing OpenGL: {e}", exc_info=True)

    def paintGL(self):
        """Render the shader."""
        if not OPENGL_AVAILABLE or not self.shader_program or not self.vao:
            return

        # Clear background
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        # Bind shader program
        self.shader_program.bind()

        # Set uniforms
        elapsed_time = time.time() - self.start_time
        speed = self.config.get("speed", 1.0)
        scale = self.config.get("scale", 1.0)

        self.shader_program.setUniformValue("time", float(elapsed_time))
        self.shader_program.setUniformValue("speed", float(speed))
        self.shader_program.setUniformValue("scale", float(scale))
        self.shader_program.setUniformValue("resolution", float(self.width()), float(self.height()))

        # Set colors
        num_colors = min(len(self.colors), 3)
        self.shader_program.setUniformValue("numColors", num_colors)
        for i in range(num_colors):
            self.shader_program.setUniformValue(f"colors[{i}]", *self.colors[i])

        # Draw fullscreen quad
        self.vao.bind()
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)  # 6 vertices (2 triangles)
        self.vao.release()

        self.shader_program.release()

    def resizeGL(self, w, h):
        """Handle resize events."""
        if OPENGL_AVAILABLE:
            GL.glViewport(0, 0, w, h)

    def cleanup(self):
        """Clean up OpenGL resources."""
        if self.vao:
            self.vao.destroy()
            self.vao = None

        if self.vbo:
            self.vbo.destroy()
            self.vbo = None

        if self.shader_program:
            self.shader_program = None


class OverlayBackgroundShader:
    """Handles shader backgrounds for overlay panel."""

    def __init__(self, shader_config: dict, parent_widget):
        self.config = shader_config
        self.parent = parent_widget
        self.widget = None

        if not self.config.get("enabled", False):
            return

        if not OPENGL_AVAILABLE:
            logging.error("OverlayBackgroundShader: PyOpenGL not installed. Cannot create shader background.")
            logging.info("Install PyOpenGL with: pip install PyOpenGL")
            return

        self._create_shader_widget()

    def _create_shader_widget(self):
        """Create the shader widget."""
        try:
            self.widget = ShaderWidget(self.parent, self.config)

            # Apply opacity using QGraphicsOpacityEffect (works for child widgets)
            opacity = self.config.get("opacity", 1.0)
            if opacity < 1.0:
                opacity_effect = QGraphicsOpacityEffect()
                opacity_effect.setOpacity(opacity)
                self.widget.setGraphicsEffect(opacity_effect)

            # Set as background
            self.widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            logging.info(f"OverlayBackgroundShader: Created shader widget with preset '{self.config.get('preset', 'plasma')}'")

        except Exception as e:
            logging.error(f"OverlayBackgroundShader: Error creating shader widget: {e}", exc_info=True)

    def get_widget(self):
        """Get the shader widget."""
        return self.widget

    def cleanup(self):
        """Clean up resources."""
        if self.widget:
            if hasattr(self.widget, 'timer'):
                self.widget.timer.stop()
            if hasattr(self.widget, 'cleanup'):
                self.widget.cleanup()
            self.widget.setParent(None)
            self.widget.deleteLater()
            self.widget = None
