/**
 * A small inline spinner for buttons in loading states.
 *
 * Renders a 16x16 spinner styled entirely via CSS (the `.button-spinner`
 * class in styles.css). Takes up space even when not spinning so button
 * widths stay stable.
 */
export function ButtonSpinner() {
  return <span className="button-spinner" aria-hidden="true" />;
}
