#version 330 core

// This shader is reserved for future advanced selection rendering.
// Currently selection is handled in fragment.glsl via the uSelectionMask sampler.

in vec2 vUV;
uniform sampler2D uSelectionMask;
uniform float uTime;
uniform vec2 uTexSize;

out vec4 FragColor;

void main() {
    float sel = texture(uSelectionMask, vUV).r;

    // Marching ants for selection boundary
    float edge = 0.0;
    vec2 texel = 1.0 / uTexSize;
    float center = sel;
    float left   = texture(uSelectionMask, vUV + vec2(-texel.x, 0.0)).r;
    float right  = texture(uSelectionMask, vUV + vec2( texel.x, 0.0)).r;
    float up     = texture(uSelectionMask, vUV + vec2(0.0, -texel.y)).r;
    float down   = texture(uSelectionMask, vUV + vec2(0.0,  texel.y)).r;

    // Detect edges in the selection mask
    edge = abs(center - left) + abs(center - right) + abs(center - up) + abs(center - down);
    edge = clamp(edge, 0.0, 1.0);

    if (edge > 0.1) {
        float ant = sin((gl_FragCoord.x + gl_FragCoord.y + uTime * 200.0) * 0.2);
        float bw = ant > 0.0 ? 1.0 : 0.0;
        FragColor = vec4(vec3(bw), 0.8);
    } else {
        FragColor = vec4(0.0);
    }
}
