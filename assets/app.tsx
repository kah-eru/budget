import "./app.css";
import { animate } from "motion/mini";

// No global Flowbite initializer: React will own only dedicated future mounts.
// Confirmed text is always server-rendered, including when scripts fail.
if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.querySelectorAll<HTMLElement>("[data-feedback]").forEach((element) => {
    animate(element, { backgroundColor: ["#e5e7eb", "#ffffff"] }, { duration: 0.2 });
  });
}
