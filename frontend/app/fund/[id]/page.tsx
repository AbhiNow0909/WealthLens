type Props = { params: Promise<{ id: string }> };

export default async function FundDetailPage({ params }: Props) {
  const { id } = await params;
  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
          Fund Detail
        </h1>
        <p className="text-[var(--text-secondary)] text-sm">ISIN: {id}</p>
      </div>
    </div>
  );
}
