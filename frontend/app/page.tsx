import ProcurePage from "@/app/procure/page";

/**
 * Home = Standard Setu (SIH26108).
 * Re-uses the /procure page component so the app serves the same UI at / and /procure.
 */
export default function Home() {
  return <ProcurePage />;
}
