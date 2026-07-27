# React (components + hooks)

_Additions to the `ALWAYS_RULE.md` baseline; lists only stack-specific criteria, does not repeat
the baseline._

#### 1. Bugs & logic issues

- Are loading/error states handled correctly?
- Do `useEffect`/`useMemo`/`useCallback` declare a complete dependency array, or is a dep missing
  (leading to a stale closure), or are there extra deps causing unnecessary re-runs?
- Is side-effect cleanup on component unmount complete (canceling subscriptions, removing event
  listeners, clearing timers/intervals in the `useEffect` return)?

#### 2. Security

- Is there an XSS risk via `dangerouslySetInnerHTML` (user input data rendered as HTML without
  sanitization)?
- Is data from an API validated/escaped before being displayed?

#### 3. Performance

- Is there excess re-rendering? Are props/callbacks passed down to child components wrapped in
  `useMemo`/`useCallback`/`React.memo` when needed?
- Does a rendered list (`.map()`) use a stable `key` (a real id) instead of the index when the
  list can be added to/removed from/reordered?
- Is there heavy computation re-run on every render that should be `useMemo`-ed?
- Are there unnecessary API calls (react-query/SWR should be used instead of repeated fetches)?

#### 4. Code quality

JavaScript and TypeScript are 2 equally valid base languages for React in this project (both
`.jsx` and `.tsx` are fully reviewed) — the criteria below clearly split what applies generally
versus what applies only when the file is TypeScript.

Applies to both `.jsx` and `.tsx`:

- Consider extracting a custom hook or shared component when you see duplication.
- Is state lifting/prop drilling pushed too deep through many component layers? Should Context or
  a state management library (Redux/Zustand/Recoil) be used instead?

Specific to `.tsx`/`.ts` (TypeScript) files:

- Are props/state/return types clearly defined via interface/type, avoiding overuse of `any`?
- Are generic types used sensibly for reusable components/hooks?
- Are union types/discriminated unions leveraged to rule out invalid states (instead of several
  separate booleans)?

#### 5. React specifics

- Is the component wrapped in an error boundary when it can throw (a render error, an error from a
  child)?
- Does a custom hook follow the Rules of Hooks (no hook calls inside a condition/loop)?
- Is controlled vs. uncontrolled component usage consistent?
- Is the Context API overused, causing the whole tree to re-render when only 1 part of the state
  changes?

#### 6. Maintainability & readability

- Is the component too large? Should be split up if the logic/JSX gets too long.
- Do tests use React Testing Library/Jest?
