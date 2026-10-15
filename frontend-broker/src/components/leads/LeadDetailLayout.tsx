import * as React from 'react'

export interface LeadDetailLayoutProps {
  header: React.ReactNode
  qualification: React.ReactNode
  conversation: React.ReactNode
  documents: React.ReactNode
  analysis: React.ReactNode
  breadcrumb?: React.ReactNode
}

/**
 * Two-column layout for the lead detail page, ordered like the broker's
 * workflow: qualify → read the conversation → extract documents → analyse.
 *
 * Left column (lg:col-span-2): qualification + conversation + documents.
 * Right column: analysis panel sticks to the top of the viewport so it stays
 * in sight as the broker scrolls through documents.
 */
export function LeadDetailLayout({
  header,
  qualification,
  conversation,
  documents,
  analysis,
  breadcrumb,
}: LeadDetailLayoutProps) {
  return (
    <div className="mx-auto max-w-6xl space-y-5 p-6 lg:p-8">
      {breadcrumb}
      {header}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          {qualification}
          {conversation}
          {documents}
        </div>
        <div className="lg:col-span-1">
          <div className="lg:sticky lg:top-6">{analysis}</div>
        </div>
      </div>
    </div>
  )
}
