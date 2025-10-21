export const QueryTypes = ["document", "annotation", "sentence"] as const;
export type QueryType = (typeof QueryTypes)[number];


export type SearchResults = {
	
}