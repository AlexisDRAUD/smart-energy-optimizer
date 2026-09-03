export function PlaceholderPage({ title, description }: Readonly<{ title: string; description: string }>) {
    return <section className="section-placeholder"><h2>{title}</h2><p>{description}</p></section>
}
