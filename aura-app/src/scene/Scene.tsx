import { useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { Core } from "./Core";
import { Particles } from "./Particles";
export type Drive = {
  color: THREE.Color;
  level: number;
  spin: number;
  amp: number;
  open: number;
  reactor: {
    color: THREE.Color;
    scale: number;
    intensity: number;
    spin: number;
    style: number;
    visible: boolean;
  };
};
function Rig({
  active,
  level,
  theme,
}: {
  active: boolean;
  level: number;
  theme: string;
}) {
  const drive = useMemo<Drive>(
    () => ({
      color: new THREE.Color("#b6a5ff"),
      level: 0,
      spin: 0.3,
      amp: 0.04,
      open: 1.6,
      reactor: {
        color: new THREE.Color("#b6a5ff"),
        scale: 1,
        intensity: 1,
        spin: 1,
        style: 1,
        visible: true,
      },
    }),
    [],
  );
  useFrame((state) => {
    drive.level = level + (active ? 0.15 : 0.025);
    drive.spin = active ? 1.5 : 0.3;
    drive.color.set(theme === "hologram" ? "#69e4ed" : "#b6a5ff");
    drive.reactor.color.copy(drive.color);
    drive.reactor.style = theme === "hologram" ? 0 : 1;
    drive.open = 1.6;
    state.camera.lookAt(0, 0, 0);
  });
  return (
    <>
      <Core drive={drive} />
      <Particles drive={drive} />
    </>
  );
}
export function Scene(props: {
  active: boolean;
  level: number;
  theme: string;
}) {
  return (
    <Canvas
      camera={{ position: [0, 0, 6.2], fov: 45 }}
      dpr={[1, 1.5]}
      gl={{ alpha: true, antialias: false }}
    >
      <Rig {...props} />
    </Canvas>
  );
}
