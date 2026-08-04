# React (components + hooks)

#### 1. Bugs & logic

- Loading/error states handled correctly?
- `useEffect`/`useMemo`/`useCallback` declare a complete dependency array — missing dep (stale
  closure)? Extra deps causing unnecessary re-runs?
- Side-effect cleanup on component unmount complete (canceling subscriptions, removing event
  listeners, clearing timers/intervals in the `useEffect` return)?

#### 2. Security

- XSS risk via `dangerouslySetInnerHTML` (user input rendered as HTML without sanitization)?
- Data from an API validated/escaped before being displayed?

#### 3. Performance

- Excess re-rendering? Props/callbacks passed to child components wrapped in
  `useMemo`/`useCallback`/`React.memo` when needed?
- Rendered list (`.map()`) uses a stable `key` (a real id) instead of the index when the list can
  be added to/removed from/reordered?
- Heavy computation re-run on every render that should be `useMemo`-ed?
- Unnecessary API calls (react-query/SWR should replace repeated fetches)?

#### 4. Code quality

Both `.jsx` and `.tsx` are fully reviewed here; the split below marks which criteria are `.tsx`-only.

Applies to both `.jsx` and `.tsx`:

- Consider extracting a custom hook or shared component when you see duplication.
- State lifting/prop drilling pushed too deep through many component layers? Should Context or a
  state management library (Redux/Zustand/Recoil) be used instead?

Specific to `.tsx`/`.ts` (TypeScript) files:

- Props/state/return types clearly defined via interface/type, avoiding overuse of `any`?
- Generic types used sensibly for reusable components/hooks?
- Union types/discriminated unions leveraged to rule out invalid states (instead of several
  separate booleans)?

#### 5. React specifics

- Component wrapped in an error boundary when it can throw (a render error, an error from a
  child)?
- Custom hook follows the Rules of Hooks (no hook calls inside a condition/loop)?
- Controlled vs. uncontrolled component usage consistent?
- Context API overused, causing the whole tree to re-render when only 1 part of the state
  changes?

#### 6. Maintainability & readability

- Component too large? Should split up if the logic/JSX gets too long.
- Tests use React Testing Library/Jest?
