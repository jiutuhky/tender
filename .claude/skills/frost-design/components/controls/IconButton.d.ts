import * as React from "react";

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Phosphor icon name without the `ph-` prefix. */
  icon: string;
  /** Accessible label — required; also used as the tooltip title. */
  label: string;
  size?: "md" | "lg";
  /** Selected state — tints with the soft-blue backing. */
  active?: boolean;
  /** Solid blue fill (e.g. a composer send button). */
  filled?: boolean;
  disabled?: boolean;
}

/**
 * Bare icon control for toolbars and inline affordances. Transparent at rest,
 * soft gray fill on hover, .92 press scale.
 */
export function IconButton(props: IconButtonProps): JSX.Element;
