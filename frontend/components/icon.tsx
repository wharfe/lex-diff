export function Icon({
  name,
  size = 18,
  className = "",
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={`material-symbols-rounded align-middle leading-none ${className}`}
      style={{ fontSize: size }}
    >
      {name}
    </span>
  );
}
