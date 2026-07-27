import { Construction } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { EmptyState } from '@/components/ui/Misc'

export function PlaceholderPage({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />
      <div className="card">
        <EmptyState
          icon={Construction}
          title={`${title} — coming in a later phase`}
          description="This surface is part of the Vector roadmap. The People, Companies, Sequences, and Analytics views are fully built with live sample data."
        />
      </div>
    </div>
  )
}
