// Motion's layout/projection feature set, kept out of the initial bundle.
//
// MotionProvider loads `domAnimation` synchronously, which covers variants,
// whileInView and AnimatePresence — everything the site animates today.
// Layout animation (`layout`, `layoutId`) needs `domMax`, which is larger, so
// it is only ever reached through a dynamic import:
//
//   <LazyMotion features={() => import("@/components/motion/features")}>
//
// Nothing references this module yet. T3.6(b) is its first intended consumer,
// and only if it passes the gate in the spec: domMax absent from the initial
// chunk, 60fps on a mid-range Android, and no layout-projection distortion in
// Safari inside the 3D-tilted stage.
export { domMax as default } from "motion/react";
