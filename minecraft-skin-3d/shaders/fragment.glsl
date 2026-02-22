#version 330 core

in vec2 vUV;
in vec3 vNormal;
in vec3 vWorldPos;

uniform sampler2D uTexture;
uniform sampler2D uSelectionMask;
uniform bool uHasSelection;
uniform float uTime;

uniform bool uShowGrid;
uniform vec2 uHoverPixel;   // (-1, -1) if no hover
uniform vec2 uTexSize;      // (64, 64) typically

out vec4 FragColor;

void main() {
    vec4 texColor = texture(uTexture, vUV);

    if (texColor.a < 0.01) {
        discard;
    }

    // Simple directional lighting
    vec3 lightDir = normalize(vec3(0.3, 1.0, 0.5));
    vec3 norm = normalize(vNormal);
    float diffuse = max(dot(norm, lightDir), 0.0);
    float ambient = 0.45;
    float light = ambient + (1.0 - ambient) * diffuse;

    vec3 lit = texColor.rgb * light;

    // Selection overlay: GIMP-style marching ants on selection boundary
    if (uHasSelection) {
        vec2 ts = 1.0 / uTexSize;          // texel size in UV space
        float sel  = texture(uSelectionMask, vUV).r;
        float selL = texture(uSelectionMask, vUV + vec2(-ts.x, 0.0)).r;
        float selR = texture(uSelectionMask, vUV + vec2( ts.x, 0.0)).r;
        float selT = texture(uSelectionMask, vUV + vec2(0.0, -ts.y)).r;
        float selB = texture(uSelectionMask, vUV + vec2(0.0,  ts.y)).r;

        // Per-edge boundary flags (neighbour differs from this texel)
        vec2 f  = fract(vUV * uTexSize);
        float bw = clamp(
            max(fwidth(vUV.x * uTexSize.x),
                fwidth(vUV.y * uTexSize.y)) * 1.5,
            0.03, 0.15);

        bool brdL = (abs(sel - selL) > 0.5) && f.x < bw;
        bool brdR = (abs(sel - selR) > 0.5) && (1.0 - f.x) < bw;
        bool brdT = (abs(sel - selT) > 0.5) && f.y < bw;
        bool brdB = (abs(sel - selB) > 0.5) && (1.0 - f.y) < bw;

        if (brdL || brdR || brdT || brdB) {
            float perim;
            if      (brdT) perim = f.x;
            else if (brdR) perim = 1.0 + f.y;
            else if (brdB) perim = 3.0 - f.x;
            else           perim = 4.0 - f.y;

            float ant = step(0.5, fract(perim * 3.0 - uTime * 2.0));
            lit = vec3(ant);
        }
    }

    // Grid overlay
    if (uShowGrid) {
        vec2 pixelCoord = vUV * uTexSize;
        vec2 grid = abs(fract(pixelCoord) - 0.5);
        float lineWidth = 0.05;
        if (grid.x > 0.5 - lineWidth || grid.y > 0.5 - lineWidth) {
            lit = mix(lit, vec3(0.2, 0.2, 0.2), 0.4);
        }
    }

    // Hover pixel highlight — GIMP-style marching ants
    if (uHoverPixel.x >= 0.0) {
        vec2 pixelCoord = floor(vUV * uTexSize);
        if (pixelCoord.x == uHoverPixel.x && pixelCoord.y == uHoverPixel.y) {
            vec2 f = fract(vUV * uTexSize);

            float dL = f.x;
            float dR = 1.0 - f.x;
            float dT = f.y;
            float dB = 1.0 - f.y;
            float edgeDist = min(min(dL, dR), min(dT, dB));

            // ~1.5 screen-pixels wide, clamped for extreme zoom levels
            float bw = clamp(
                max(fwidth(vUV.x * uTexSize.x),
                    fwidth(vUV.y * uTexSize.y)) * 1.5,
                0.03, 0.15);

            if (edgeDist < bw) {
                // Perimeter position (0‥4, one unit per edge, clockwise)
                float perim;
                if      (dT <= dB && dT <= dL && dT <= dR) perim = f.x;
                else if (dR <= dL && dR <= dT && dR <= dB) perim = 1.0 + f.y;
                else if (dB <= dT && dB <= dL && dB <= dR) perim = 3.0 - f.x;
                else                                        perim = 4.0 - f.y;

                // 3 dash-pairs per edge, marching at moderate speed
                float ant = step(0.5, fract(perim * 3.0 - uTime * 2.0));
                lit = vec3(ant);
            }
        }
    }

    FragColor = vec4(lit, texColor.a);
}
