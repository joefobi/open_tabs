import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Sidebar } from "./sidebar";
import "./sidebar.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode><Sidebar /></StrictMode>,
);
