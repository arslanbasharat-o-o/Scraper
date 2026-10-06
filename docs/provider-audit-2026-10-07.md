# Live provider audit — 2026-10-07

The live category audit sampled 30 category URLs per supplier target (240 unique URLs total), with one listing page per category. Where a category returned products, the audit independently checked one product page and compared its title, SKU, price, and link to the listing. The audit used a direct connection with no proxy.

| Provider target | Categories | Result |
| --- | ---: | --- |
| MobileSentrix US | 30 | 29 verified; 1 category could not be verified because its JavaScript page had no usable browser fallback |
| MobileSentrix Canada | 30 | 30 verified |
| XCellParts | 30 | 24 verified; 6 requests were blocked or returned unusable responses (HTTP 403 observed) |
| TXParts US | 30 | 30 verified |
| TXParts Canada | 30 | 24 verified; 5 had no independently available live price; 1 category returned no products |
| Parts4Cells | 30 | 29 verified; 1 had no independently available live price |
| PhoneLCDParts | 30 | 30 verified |
| GadgetFix | 30 | 30 verified |

Price-unavailable results still had matching product identity and category-link evidence. The audit also handles supplier pages that omit a visible heading by using structured SKU evidence, while keeping title, SKU presence, price, category-link, duplicate, and invalid-row checks.

## Interpretation

This is a point-in-time sample from the audit host’s network. It confirms the tested extraction paths for the verified categories; it does not guarantee access from a datacenter IP or verify every product on each site. XCellParts access was intermittent from the direct connection. Configure a proxy in the deployment environment if the server’s network is blocked, then repeat the live audit there.

The MobileSentrix US category that could not be verified returned an empty JavaScript-rendered listing over HTTP, and browser fallback did not produce usable HTML. It is now classified as a category page rather than a phantom zero-price product. TXParts Canada’s `shop/cables` category returned no products during this run.
