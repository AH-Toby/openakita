type ToastContainerProps = {
  busy: string | null;
  notice: string | null;
  error: string | null;
  onDismissNotice: () => void;
  onDismissError: () => void;
};

export function ToastContainer({ busy, notice, error, onDismissNotice, onDismissError }: ToastContainerProps) {
  if (!busy && !notice && !error) return null;
  return (
    <div className="toastContainer">
      {busy && <div className="toast toastInfo">{busy}</div>}
      {notice && <div className="toast toastOk" onClick={onDismissNotice}>{notice}</div>}
      {error && <div className="toast toastError" onClick={onDismissError}>{error}</div>}
    </div>
  );
}
