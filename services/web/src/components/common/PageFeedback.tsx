export function PageFeedback({ isLoading, error, onRetry }: Readonly<{ isLoading: boolean; error: string | null; onRetry: () => void }>) {
    if (isLoading) return <div className="page-feedback" role="status">Chargement des données…</div>
    if (error) return <div className="page-feedback error" role="alert"><span>{error}</span><button type="button" onClick={onRetry}>Réessayer</button></div>
    return null
}
