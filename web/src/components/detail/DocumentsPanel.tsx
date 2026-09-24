import { FileCheck2, FileQuestion, FileText, FileX2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import type { BidDocument, OcrResult } from "@/lib/api";
import { documentTypeLabel, formatDateTime, formatValue } from "@/lib/format";

const OCR_METHOD: Record<string, string> = {
  pdf_text_layer: "PDF text layer",
  tesseract: "Tesseract OCR",
  pdf_tesseract: "Scanned PDF · Tesseract",
};

export function DocumentsPanel({ documents }: { documents: BidDocument[] }) {
  return (
    <Card>
      <CardHeader title="Documents" description="What the bidder submitted, and what OCR read from each upload." />
      {documents.length === 0 ? (
        <CardBody className="text-sm text-slate-500">No document submissions recorded.</CardBody>
      ) : (
        <ul className="divide-y divide-slate-100">
          {documents.map((doc) => (
            <DocumentRow key={doc.document_type} doc={doc} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function DocumentRow({ doc }: { doc: BidDocument }) {
  const Icon = !doc.submitted ? FileX2 : doc.is_placeholder ? FileText : doc.ocr?.status === "extracted" ? FileCheck2 : FileQuestion;
  const fields = Object.entries(doc.ocr?.fields ?? {});

  return (
    <li className="px-5 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2.5">
          <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${doc.submitted ? "text-slate-500" : "text-red-600"}`} aria-hidden />
          <div>
            <div className="text-sm font-medium text-slate-900">{documentTypeLabel(doc.document_type)}</div>
            <div className="text-xs text-slate-500">
              {!doc.submitted
                ? doc.note ?? "Not submitted"
                : doc.is_placeholder
                  ? "Seeded reference — no file uploaded"
                  : doc.uploaded_at
                    ? `Uploaded ${formatDateTime(doc.uploaded_at)}`
                    : "Uploaded"}
              {doc.submitted && doc.note && ` · ${doc.note}`}
            </div>
          </div>
        </div>
        <DocumentStatus doc={doc} />
      </div>

      {fields.length > 0 && (
        <dl className="ml-6 mt-2 grid grid-cols-1 gap-x-4 gap-y-1 rounded-md bg-slate-50 px-3 py-2 text-xs sm:grid-cols-2">
          {fields.map(([key, value]) => (
            <div key={key} className="flex gap-2">
              <dt className="text-slate-500">{key.replace(/_/g, " ")}</dt>
              <dd className="font-medium text-slate-800">{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      {doc.ocr?.error && <p className="ml-6 mt-1.5 text-xs text-red-700">{doc.ocr.error}</p>}
      {doc.ocr?.text_excerpt && (
        <details className="ml-6 mt-1.5 text-xs">
          <summary className="cursor-pointer text-slate-500 hover:text-slate-700">Extracted text</summary>
          <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-2 font-mono text-[11px] text-slate-700">
            {doc.ocr.text_excerpt}
          </pre>
        </details>
      )}
    </li>
  );
}

function DocumentStatus({ doc }: { doc: BidDocument }) {
  if (!doc.submitted) return <Badge tone="danger">Missing</Badge>;
  if (doc.is_placeholder) return <Badge tone="neutral">Placeholder</Badge>;
  if (!doc.ocr) return <Badge tone="info">OCR pending</Badge>;
  return <OcrBadge ocr={doc.ocr} />;
}

function OcrBadge({ ocr }: { ocr: OcrResult }) {
  const method = ocr.method ? OCR_METHOD[ocr.method] ?? ocr.method : null;
  switch (ocr.status) {
    case "extracted":
      return <Badge tone="success">Read · {method}</Badge>;
    case "no_text":
      return <Badge tone="warning">No text found</Badge>;
    case "ocr_unavailable":
      return <Badge tone="warning">OCR unavailable</Badge>;
    default:
      return <Badge tone="danger">Unreadable</Badge>;
  }
}
