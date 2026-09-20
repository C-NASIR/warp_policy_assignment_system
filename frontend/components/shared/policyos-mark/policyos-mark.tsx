import Image from "next/image";

export function PolicyOSMark({
  className,
  size = 29,
  decorative = true,
  label = "PolicyOS",
}: {
  className?: string;
  size?: number;
  decorative?: boolean;
  label?: string;
}) {
  return (
    <Image
      className={className}
      src="/brand/policyos-mark.svg"
      width={size}
      height={size}
      alt={decorative ? "" : label}
      aria-hidden={decorative || undefined}
      priority
    />
  );
}
