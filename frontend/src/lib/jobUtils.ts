export function foldTags(
  tags: string[],
  maxVisible = 2,
): { visible: string[]; hidden: string[]; remaining: number } {
  const visible = tags.slice(0, maxVisible);
  const hidden = tags.slice(maxVisible);
  return { visible, hidden, remaining: hidden.length };
}
