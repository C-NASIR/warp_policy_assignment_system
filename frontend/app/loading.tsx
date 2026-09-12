import styles from "./loading.module.css";

export default function Loading() {
  return (
    <div className={styles.loading} aria-label="Loading page" aria-busy="true">
      <div className="skeleton skeleton-title" />
      <div className="metric-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="skeleton skeleton-card" key={index} />
        ))}
      </div>
      <span className="sr-only">Loading policy assignment data</span>
    </div>
  );
}
