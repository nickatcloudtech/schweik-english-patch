import React from "react";
import { createRoot } from "react-dom/client";
import SvejkTranslator from "../../svejk-translator.jsx";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <SvejkTranslator />
  </React.StrictMode>
);