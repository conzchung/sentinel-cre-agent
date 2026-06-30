// Themed SVG line-icons. Single source of truth so the UI never falls back to
// emoji (which don't match the palette). Every icon inherits `currentColor`,
// so colour is controlled entirely by CSS on the parent.

import type { ToolIconKey } from '@/lib/types';

type IconProps = { size?: number; className?: string };

function svg(size: number, className: string | undefined, children: React.ReactNode) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const SkillIcon = ({ size = 15, className }: IconProps) =>
  svg(size, className, (
    <>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </>
  ));

export const DataIcon = ({ size = 15, className }: IconProps) =>
  svg(size, className, (
    <>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5" />
      <path d="M3 12c0 1.7 4 3 9 3s9-1.3 9-3" />
    </>
  ));

export const ChartIcon = ({ size = 15, className }: IconProps) =>
  svg(size, className, (
    <>
      <path d="M3 3v18h18" />
      <path d="M7 15l3-4 3 2 4-6" />
    </>
  ));

export const WebIcon = ({ size = 15, className }: IconProps) =>
  svg(size, className, (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </>
  ));

export const KnowledgeIcon = ({ size = 15, className }: IconProps) =>
  svg(size, className, (
    <>
      <path d="M4 4v15a2 2 0 0 1 2-2h14" />
      <path d="M6 2h14v18H6a2 2 0 0 0-2 2V4a2 2 0 0 1 2-2z" />
      <path d="M9 7h7M9 11h5" />
    </>
  ));

export const ReportIcon = ({ size = 15, className }: IconProps) =>
  svg(size, className, (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M9 13h6M9 17h6M9 9h1" />
    </>
  ));

export const PlanIcon = ({ size = 15, className }: IconProps) =>
  svg(size, className, (
    <>
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </>
  ));

export const ToolIcon = ({ size = 15, className }: IconProps) =>
  svg(size, className, (
    <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.7 2.7-2-2 2.7-2.7z" />
  ));

export const PlusIcon = ({ size = 16, className }: IconProps) =>
  svg(size, className, <path d="M12 5v14M5 12h14" />);

export const TrashIcon = ({ size = 14, className }: IconProps) =>
  svg(size, className, (
    <>
      <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
    </>
  ));

export const SendIcon = ({ size = 16, className }: IconProps) =>
  svg(size, className, <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />);

export const SparkIcon = ({ size = 13, className }: IconProps) =>
  svg(size, className, (
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18" />
  ));

export const LogoutIcon = ({ size = 14, className }: IconProps) =>
  svg(size, className, (
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </>
  ));

export const CheckIcon = ({ size = 13, className }: IconProps) =>
  svg(size, className, <path d="M20 6L9 17l-5-5" />);

export const CloseIcon = ({ size = 13, className }: IconProps) =>
  svg(size, className, <path d="M18 6L6 18M6 6l12 12" />);

export const MenuIcon = ({ size = 18, className }: IconProps) =>
  svg(size, className, <path d="M3 6h18M3 12h18M3 18h18" />);

const TOOL_ICON: Record<ToolIconKey, (p: IconProps) => React.ReactElement> = {
  skill: SkillIcon,
  data: DataIcon,
  chart: ChartIcon,
  web: WebIcon,
  knowledge: KnowledgeIcon,
  report: ReportIcon,
  plan: PlanIcon,
  tool: ToolIcon,
};

/** Render the icon for a given tool-icon key. */
export function ToolGlyph({ name, size = 15, className }: { name: ToolIconKey } & IconProps) {
  const Cmp = TOOL_ICON[name] ?? ToolIcon;
  return <Cmp size={size} className={className} />;
}
