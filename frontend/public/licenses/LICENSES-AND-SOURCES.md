# Frontend licenses and sources

Verified 2026-10-26 against installed package notices. Versions are pinned in frontend/package-lock.json. Font files are bundled and served by this app; no Google Fonts/CDN request is made at runtime. Full notices ship in frontend/public/licenses/ and are copied into production output by Vite.

| Piece | Installed version / use | Source | License / notice |
|---|---|---|---|
| Space Grotesk | @fontsource/space-grotesk 5.3.0; Latin 500 WOFF2, display | [Upstream](https://github.com/floriankarsten/space-grotesk), [license](https://github.com/floriankarsten/space-grotesk/blob/master/OFL.txt), [Fontsource](https://fontsource.org/fonts/space-grotesk) | SIL OFL 1.1; public/licenses/space-grotesk-OFL.txt, copied unmodified from installed package |
| Source Sans 3 | @fontsource/source-sans-3 5.3.1; Latin 400/600 WOFF2, text | [Upstream](https://github.com/adobe-fonts/source-sans), [license](https://github.com/adobe-fonts/source-sans/blob/release/LICENSE.md), [Fontsource](https://fontsource.org/fonts/source-sans-3) | SIL OFL 1.1; public/licenses/source-sans-3-OFL.txt, copied unmodified from installed package |
| IBM Plex Mono | @fontsource/ibm-plex-mono 5.3.0; Latin 400 WOFF2 loaded in Stage 3 and used only in the technical drawer; not shipped in Stage 1/2 | [Upstream](https://github.com/IBM/plex), [license](https://github.com/IBM/plex/blob/master/LICENSE.txt), [Fontsource](https://fontsource.org/fonts/ibm-plex-mono) | SIL OFL 1.1; public/licenses/ibm-plex-mono-OFL.txt, copied unmodified from installed package |
| Motion | 14.6.0; user-triggered lock shackle, lazy chunk | [Repository](https://github.com/motiondivision/motion), [docs](https://motion.dev/docs/react) | MIT; public/licenses/motion-MIT.txt |
| Framer Motion | 14.6.0; Motion React implementation | [Repository](https://github.com/motiondivision/motion) | MIT; public/licenses/framer-motion-MIT.txt |
| motion-dom | 14.6.0; animation runtime | [Repository](https://github.com/motiondivision/motion) | MIT; public/licenses/motion-dom-MIT.txt |
| motion-utils | 14.6.0; animation helpers | [Repository](https://github.com/motiondivision/motion) | MIT; public/licenses/motion-utils-MIT.txt |
| tslib | 2.8.1; Motion dependency | [Repository](https://github.com/microsoft/tslib) | 0BSD; public/licenses/tslib-0BSD.txt, plus tslib-CopyrightNotice.txt |
| React / React DOM | 19.3.1; retained toolchain, rendering | [Repository](https://github.com/facebook/react) | MIT; public/licenses/react-MIT.txt and react-dom-MIT.txt |
| scheduler | 0.28.0; React DOM dependency | [Repository](https://github.com/facebook/react) | MIT; public/licenses/scheduler-MIT.txt |
| react-router-dom / react-router | 7.18.4; declarative workbench routing | [Upstream](https://github.com/remix-run/react-router), [BrowserRouter docs](https://reactrouter.com/api/declarative-routers/BrowserRouter) | MIT; public/licenses/react-router-dom-MIT.txt and react-router-MIT.txt |
| cookie | 1.1.1; React Router dependency | [Upstream](https://github.com/jshttp/cookie) | MIT; public/licenses/cookie-MIT.txt |
| set-cookie-parser | 2.7.3; React Router dependency | [Upstream](https://github.com/nfriedly/set-cookie-parser) | MIT; public/licenses/set-cookie-parser-MIT.txt |
| Lock illustration | Original inline SVG geometry, material shading and interaction; src/components/lock/LockObject.tsx | Authored for this project; no reference asset copied | Project-authored artwork; no separate third-party asset |
| Interface icons and favicon | Original SVG paths in Icon.tsx and public/favicon.svg | Authored for this project; no icon pack copied | Project-authored artwork; no separate third-party asset |
| Buttons, marks, theme control, choice controls and layout | Original React/CSS; native controls and shared tokens | Authored for this project; no component kit copied | Project-authored UI; no separate third-party component |

The installed Fontsource Source Sans notice identifies Google Inc.; it is preserved verbatim rather than rewritten. The canonical Adobe upstream license is linked above. Fonts are unmodified; reserved font names are retained only for the original families. Font redistribution follows the included OFL notices; no font is sold independently.

No Animate UI, Uiverse, VibeUI, Aceternity, Magic UI, Inspira UI or stock artwork is included. The owner skipped the landing page, so Lenis is omitted. The unused scaffold public icon sprite was removed; unused source-only scaffold illustrations are not imported into the build. The style tile remains development-only. Stage 3 ships the original lock as a lazy chunk for the execution sequence and blocked result. Motion also animates exact token balances; no borrowed UI component or artwork was added.

Build tooling is inherited: Vite and @vitejs/plugin-react (MIT), TypeScript (Apache 2.0), Oxlint (MIT), and TypeScript definition packages (MIT). Their installed notices remain with their npm packages; they are not browser-runtime code. No claim is made that this document is a legal review.

Accessibility implementation references: [Motion reduced-motion configuration](https://motion.dev/docs/react-motion-config), [useReducedMotion](https://motion.dev/docs/react-use-reduced-motion). Components are original implementations, not copied documentation examples.
