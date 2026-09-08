import type { ReactNode } from 'react'

export type Column<Row> = {
    header: string
    cell: (row: Row) => ReactNode
}

type DataTableProps<Row> = {
    columns: Column<Row>[]
    rows: Row[]
    rowKey: (row: Row) => string
    emptyLabel: string
}

/** Tableau simple. Il défile horizontalement quand la place manque. */
export function DataTable<Row>({ columns, rows, rowKey, emptyLabel }: Readonly<DataTableProps<Row>>) {
    if (!rows.length) {
        return <p className="empty-state">{emptyLabel}</p>
    }

    return (
        <div className="table-scroll">
            <table>
                <thead>
                    <tr>
                        {columns.map((column) => <th key={column.header}>{column.header}</th>)}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row) => (
                        <tr key={rowKey(row)}>
                            {columns.map((column) => <td key={column.header}>{column.cell(row)}</td>)}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}
