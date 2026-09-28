"use client";

/* eslint-disable react/no-unknown-property */
import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { cn } from "@/lib/utils";

// --- Shader: dithered diagonal gradient (Bayer 4x4 + simplex noise) ---
// Adapted to the Standard Setu manuscript palette: deep ink flows to paper
// with hard poster-like steps and a fine dithered grain on the boundaries.

const vertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const fragmentShader = `
uniform float uTime;
uniform vec2 uResolution;
uniform vec3 uColor1;
uniform vec3 uColor2;
varying vec2 vUv;

vec3 permute(vec3 x) { return mod(((x*34.0)+1.0)*x, 289.0); }

float snoise(vec2 v){
  const vec4 C = vec4(0.211324865405187, 0.366025403784439,
           -0.577350269189626, 0.024390243902439);
  vec2 i  = floor(v + dot(v, C.yy) );
  vec2 x0 = v -   i + dot(i, C.xx);
  vec2 i1;
  i1 = (x0.x > x0.y) ? vec4(1.0, 0.0, 0.0, 1.0).xy : vec4(0.0, 1.0, 1.0, 0.0).xy;
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod(i, 289.0);
  vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 ))
  + i.x + vec3(0.0, i1.x, 1.0 ));
  vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
  m = m*m ;
  m = m*m ;
  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
  vec3 g;
  g.x  = a0.x  * x0.x  + h.x  * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

float bayerDither4x4(vec2 uv) {
    int x = int(mod(uv.x, 4.0));
    int y = int(mod(uv.y, 4.0));

    int matrix[16];
    matrix[0] = 0; matrix[1] = 8; matrix[2] = 2; matrix[3] = 10;
    matrix[4] = 12; matrix[5] = 4; matrix[6] = 14; matrix[7] = 6;
    matrix[8] = 3; matrix[9] = 11; matrix[10] = 1; matrix[11] = 9;
    matrix[12] = 15; matrix[13] = 7; matrix[14] = 13; matrix[15] = 5;

    return float(matrix[y * 4 + x]) / 16.0;
}

void main() {
    vec2 uv = vUv;
    vec2 coord = gl_FragCoord.xy;

    // Slow breathing noise so the paper feels alive
    float noise = snoise(uv * 1.5 + vec2(uTime * 0.05, uTime * 0.03)) * 0.25;

    // Diagonal gradient from bottom-left (deep ink) to top-right (paper)
    float diagonal = (uv.x + uv.y) * 0.5;
    float gradient = diagonal * 1.2 + noise;

    vec3 deepInk = uColor1;
    vec3 paper   = uColor2;
    vec3 step1 = mix(deepInk, paper, 0.33);
    vec3 step2 = mix(deepInk, paper, 0.66);

    vec3 color;
    if (gradient < 0.3) {
        color = deepInk;
    } else if (gradient < 0.55) {
        color = step1;
    } else if (gradient < 0.8) {
        color = step2;
    } else {
        color = paper;
    }

    // Dithered boundaries between the poster steps
    float dither = bayerDither4x4(coord);
    float threshold = fract(gradient * 4.0);

    if (gradient < 0.3 && threshold > dither * 0.5) {
        color = step1;
    } else if (gradient >= 0.3 && gradient < 0.55 && threshold > dither * 0.5) {
        color = step2;
    } else if (gradient >= 0.55 && gradient < 0.8 && threshold > dither * 0.5) {
        color = paper;
    }

    // Fade to paper-white at the extreme top-right corner only
    vec2 cornerDist = vec2(1.0 - uv.x, 1.0 - uv.y);
    float fadeMask = smoothstep(0.0, 0.25, length(cornerDist));
    color = mix(vec3(1.0), color, fadeMask);

    // Subtle vignette to emphasize corners
    float vignette = smoothstep(1.2, 0.3, length(uv - 0.5));
    color = mix(color, color * 0.95, (1.0 - vignette) * 0.3);

    gl_FragColor = vec4(color, 1.0);
}
`;

const FALLBACK_COLOR_1 = "#1c2438"; // ink
const FALLBACK_COLOR_2 = "#f1efe6"; // paper
const HEX_COLOR_REGEX = /^#?[0-9a-fA-F]{6}$/;

function sanitizeHexColor(value: string, fallback: string) {
  const trimmed = value.trim();
  if (!HEX_COLOR_REGEX.test(trimmed)) return fallback;
  return trimmed.startsWith("#") ? trimmed : `#${trimmed}`;
}

function GradientPlane({
  color1,
  color2,
  speed = 1,
}: {
  color1: string;
  color2: string;
  speed?: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uResolution: { value: new THREE.Vector2(1000, 1000) },
      uColor1: { value: new THREE.Color(FALLBACK_COLOR_1) },
      uColor2: { value: new THREE.Color(FALLBACK_COLOR_2) },
    }),
    []
  );

  useFrame((state) => {
    const { clock, size } = state;
    uniforms.uTime.value = clock.getElapsedTime() * speed;
    uniforms.uResolution.value.set(size.width, size.height);
    uniforms.uColor1.value.set(sanitizeHexColor(color1, FALLBACK_COLOR_1));
    uniforms.uColor2.value.set(sanitizeHexColor(color2, FALLBACK_COLOR_2));
  });

  return (
    <mesh ref={meshRef} scale={[2, 2, 1]}>
      <planeGeometry args={[2, 2]} />
      <shaderMaterial
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent={true}
        depthWrite={false}
        depthTest={false}
      />
    </mesh>
  );
}

export interface HeroGeometricProps extends React.HTMLAttributes<HTMLDivElement> {
  color1?: string;
  color2?: string;
  speed?: number;
  children?: React.ReactNode;
}

/**
 * Dithered-gradient WebGL backdrop (three.js / react-three-fiber).
 * Used behind the agent landing state; content renders on top via children.
 */
export default function HeroGeometric({
  color1 = "#1c2438",
  color2 = "#f1efe6",
  speed = 1,
  className,
  children,
  ...props
}: HeroGeometricProps) {
  return (
    <div
      className={cn("relative w-full overflow-hidden", className)}
      {...props}
    >
      {/* Background shader */}
      <div className="pointer-events-none absolute left-0 top-0 z-0 h-full w-full">
        <Canvas
          camera={{ position: [0, 0, 1] }}
          dpr={[1, 1]}
          gl={{ antialias: false, alpha: true }}
        >
          <GradientPlane color1={color1} color2={color2} speed={speed} />
        </Canvas>
      </div>

      {/* Soft ink overlay for text legibility over light gradient bands */}
      <div
        className="pointer-events-none absolute inset-0 z-[5]"
        style={{
          background:
            "linear-gradient(105deg, rgba(28,36,56,0.30) 0%, rgba(28,36,56,0.10) 48%, rgba(28,36,56,0.22) 100%)",
        }}
      />

      {/* Content sits above the shader */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}
