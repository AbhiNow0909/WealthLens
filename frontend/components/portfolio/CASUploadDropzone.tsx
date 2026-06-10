"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { createClient } from "@/lib/supabase-browser";

interface UploadResult {
  upload_id: string;
  status: string;
  funds_found: number;
  transactions_found: number;
}

interface Props {
  onSuccess?: (result: UploadResult) => void;
}

type UploadState = "idle" | "uploading" | "success" | "error";

export default function CASUploadDropzone({ onSuccess }: Props) {
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [password, setPassword] = useState("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const upload = useCallback(
    async (file: File, pwd: string) => {
      setUploadState("uploading");
      setErrorMsg(null);
      setProgress(10);

      try {
        const supabase = createClient();
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData.session?.access_token;
        if (!token) throw new Error("Not authenticated");

        setProgress(40);
        const formData = new FormData();
        formData.append("file", file);
        formData.append("password", pwd);

        setProgress(60);
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/portfolio/upload`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: formData,
          }
        );

        setProgress(90);
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail ?? "Upload failed");
        }

        const data: UploadResult = await res.json();
        setResult(data);
        setUploadState("success");
        setProgress(100);
        onSuccess?.(data);
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Upload failed");
        setUploadState("error");
        setProgress(0);
      }
    },
    [onSuccess]
  );

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) setPendingFile(accepted[0]);
    },
    []
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    disabled: uploadState === "uploading",
  });

  if (uploadState === "success" && result) {
    return (
      <div className="rounded-xl border border-[var(--gain)] bg-[var(--gain)]/10 p-6 text-center">
        <div className="text-[var(--gain)] text-2xl mb-2">✓</div>
        <p className="text-[var(--text-primary)] font-medium">CAS parsed successfully</p>
        <p className="text-[var(--text-secondary)] text-sm mt-1">
          {result.funds_found} fund{result.funds_found !== 1 ? "s" : ""} ·{" "}
          {result.transactions_found} transactions imported
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 text-xs text-[var(--accent)] hover:underline"
        >
          View portfolio →
        </button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-lg mx-auto space-y-3">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={[
          "rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-colors",
          isDragActive
            ? "border-[var(--accent)] bg-[var(--accent)]/10"
            : pendingFile
            ? "border-[var(--accent)]/60 bg-[var(--surface)]"
            : "border-[var(--border)] hover:border-[var(--accent)]/60 bg-[var(--surface)]",
          uploadState === "uploading" ? "pointer-events-none opacity-70" : "",
        ].join(" ")}
      >
        <input {...getInputProps()} />
        {uploadState === "uploading" ? (
          <div>
            <div className="text-[var(--text-secondary)] text-sm mb-3">
              Parsing your CAS statement…
            </div>
            <div className="w-full bg-[var(--border)] rounded-full h-1.5">
              <div
                className="bg-[var(--accent)] h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        ) : pendingFile ? (
          <>
            <div className="text-[var(--gain)] text-2xl mb-2">📄</div>
            <p className="text-[var(--text-primary)] text-sm font-medium truncate px-4">
              {pendingFile.name}
            </p>
            <p className="text-[var(--text-secondary)] text-xs mt-1">
              Click to choose a different file
            </p>
          </>
        ) : (
          <>
            <div className="text-3xl mb-3 text-[var(--text-secondary)]">↑</div>
            <p className="text-[var(--text-primary)] font-medium text-sm">
              {isDragActive ? "Drop your CAS PDF here" : "Drop your NSDL CAS PDF here"}
            </p>
            <p className="text-[var(--text-secondary)] text-xs mt-1">
              or click to browse · PDF only · max 20 MB
            </p>
            <p className="text-[var(--text-secondary)] text-xs mt-3">
              Download from{" "}
              <span className="text-[var(--accent)]">myCAMS · KFintech · NSDL</span>
            </p>
          </>
        )}
      </div>

      {/* Password field — shown once a file is selected */}
      {pendingFile && uploadState !== "uploading" && (
        <div>
          <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
            PDF password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Email or PAN"
            className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
          />
          <p className="mt-1.5 text-[var(--text-secondary)] text-xs leading-relaxed">
            • <span className="text-[var(--text-primary)]">NSDL CAS</span> — your registered email address{" "}
            <br />
            • <span className="text-[var(--text-primary)]">CAMS / KFintech CAS</span> — your PAN number (e.g. ABCDE1234F)
          </p>
        </div>
      )}

      {/* Upload button */}
      {pendingFile && uploadState !== "uploading" && (
        <button
          onClick={() => upload(pendingFile, password)}
          disabled={!password}
          className="w-full bg-[var(--accent)] text-white text-sm font-medium rounded-lg px-4 py-2.5 disabled:opacity-40 hover:opacity-90 transition-opacity"
        >
          Import portfolio
        </button>
      )}

      {uploadState === "error" && errorMsg && (
        <p className="text-[var(--loss)] text-xs text-center">{errorMsg}</p>
      )}
    </div>
  );
}
