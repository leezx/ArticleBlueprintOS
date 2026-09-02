SYNTHETIC_PUBMED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>40000001</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate><Year>2026</Year><Month>Aug</Month><Day>14</Day></PubDate>
          </JournalIssue>
          <Title>Synthetic Cancer Journal</Title>
        </Journal>
        <ArticleTitle>A synthetic pan-cancer single-cell transcriptomic atlas</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Synthetic tumor ecosystems are heterogeneous.</AbstractText>
          <AbstractText Label="RESULTS">Synthetic scRNA-seq and spatial data were integrated.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Example</LastName><ForeName>Ada</ForeName><Initials>A</Initials><Identifier Source="ORCID">0000-0000-0000-0001</Identifier></Author>
          <Author><CollectiveName>Synthetic Atlas Consortium</CollectiveName></Author>
        </AuthorList>
        <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Neoplasms</DescriptorName></MeshHeading>
        <MeshHeading><DescriptorName>Transcriptome</DescriptorName></MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">40000001</ArticleId>
        <ArticleId IdType="doi">10.1000/SYNTHETIC.001</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>40000002</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><MedlineDate>2025 Winter</MedlineDate></PubDate></JournalIssue>
          <Title>Synthetic Review Journal</Title>
        </Journal>
        <ArticleTitle>Synthetic concepts in oncology</ArticleTitle>
        <Abstract><AbstractText>A synthetic narrative review.</AbstractText></Abstract>
        <AuthorList><Author><LastName>Example</LastName><Initials>B</Initials></Author></AuthorList>
        <PublicationTypeList><PublicationType>Review</PublicationType></PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData><ArticleIdList><ArticleId IdType="pubmed">40000002</ArticleId></ArticleIdList></PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""
