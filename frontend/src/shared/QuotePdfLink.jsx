import { useParams } from "react-router-dom";
import { Download } from "lucide-react";

export const QuotePdfLink = ({ className = "" }) => {
  const { token } = useParams();
  return (
    <a data-testid="download-quote-pdf-btn" href={`${process.env.REACT_APP_BACKEND_URL}/api/portal/${token}/quote.pdf`} download
      className={`flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl border border-wt-line bg-white text-[16px] font-semibold text-wt-ink transition-colors duration-150 hover:border-wt-ink/30 ${className}`}>
      <Download className="h-4 w-4" /> Download PDF
    </a>
  );
};
