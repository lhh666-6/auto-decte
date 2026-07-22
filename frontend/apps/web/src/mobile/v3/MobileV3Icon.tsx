type MobileV3IconName = "home" | "work" | "submissions" | "profile";

export function MobileV3Icon({ name }: { name: MobileV3IconName }) {
  const paths: Record<MobileV3IconName, React.ReactNode> = {
    home: <><path d="m3 11 9-8 9 8" /><path d="M5 10v10h14V10" /><path d="M9 20v-6h6v6" /></>,
    work: <><path d="M7 7V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v2" /><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M3 12h18" /><path d="M9 12v2h6v-2" /></>,
    submissions: <><path d="M8 4h8" /><path d="M9 3v3h6V3" /><path d="M6 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-1" /><path d="m8 14 3 3 6-7" /></>,
    profile: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  };

  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}
