"""Curated P0 records, independently anchored to the pinned source (not discovery)."""
import hashlib
from pathlib import Path

PIN='0c2c95d9d450d07fcd4e96e95e1cd48c20834e99'
# ID, source path, exact source anchors, narrow statement, confidence.
SPECS=[
('basket.create','src/ApplicationCore/Services/BasketService.cs',['if (basket == null)','basket = new Basket(username);','await _basketRepository.AddAsync(basket);'], 'BasketService AddItemToBasket creates and saves a new basket when lookup by username returns null.', 'CONFIRMED'),
('basket.quantities','src/ApplicationCore/Services/BasketService.cs',['public async Task<Result<Basket>> SetQuantities','if (basket == null) return Result<Basket>.NotFound();'], 'BasketService SetQuantities returns NotFound when the basket lookup is null.', 'CONFIRMED'),
('basket.transfer','src/ApplicationCore/Services/BasketService.cs',['userBasket.AddItem(item.CatalogItemId, item.UnitPrice, item.Quantity);','await _basketRepository.DeleteAsync(anonymousBasket);'], 'BasketService TransferBasketAsync copies anonymous basket items into the user basket, updates it, and deletes the anonymous basket.', 'CONFIRMED'),
('basket.merge','src/ApplicationCore/Entities/BasketAggregate/Basket.cs',['var existingItem = Items.First(i => i.CatalogItemId == catalogItemId);','existingItem.AddQuantity(quantity);'], 'Basket AddItem increases quantity for an existing matching CatalogItemId instead of creating a second item.', 'CONFIRMED'),
('basket.empty','src/ApplicationCore/Entities/BasketAggregate/Basket.cs',['_items.RemoveAll(i => i.Quantity == 0);'], 'Basket RemoveEmptyItems removes items whose quantity equals zero.', 'CONFIRMED'),
('order.guard','src/ApplicationCore/Services/OrderService.cs',['Guard.Against.Null(basket, nameof(basket));','Guard.Against.EmptyBasketOnCheckout(basket.Items);'], 'OrderService CreateOrderAsync guards against a null basket and an empty basket before checkout.', 'CONFIRMED'),
('order.snapshot','src/ApplicationCore/Services/OrderService.cs',['var itemOrdered = new CatalogItemOrdered(catalogItem.Id, catalogItem.Name, _uriComposer.ComposePicUri(catalogItem.PictureUri));','var orderItem = new OrderItem(itemOrdered, basketItem.UnitPrice, basketItem.Quantity);'], 'OrderService creates OrderItem snapshots using catalog identity, name, composed picture URI, basket unit price and quantity.', 'CONFIRMED'),
('order.publish','src/ApplicationCore/Services/OrderService.cs',['await _orderRepository.AddAsync(order);','await _mediator.Publish(orderCreatedEvent);'], 'OrderService persists the order before publishing OrderCreatedEvent through the mediator.', 'CONFIRMED'),
('persistence.repository','src/Infrastructure/Data/EfRepository.cs',['public class EfRepository<T> : RepositoryBase<T>, IReadRepository<T>, IRepository<T> where T : class, IAggregateRoot','public EfRepository(CatalogContext dbContext) : base(dbContext)'], 'EfRepository implements IReadRepository and IRepository for aggregate roots using CatalogContext and RepositoryBase.', 'CONFIRMED'),
('persistence.model','src/Infrastructure/Data/CatalogContext.cs',['public DbSet<Basket> Baskets','public DbSet<Order> Orders','builder.ApplyConfigurationsFromAssembly(Assembly.GetExecutingAssembly());'], 'CatalogContext exposes Baskets and Orders DbSets and applies entity configurations from its executing assembly.', 'CONFIRMED'),
('web.services','src/Web/Configuration/ConfigureCoreServices.cs',['services.AddScoped<IBasketService, BasketService>();','services.AddScoped<IOrderService, OrderService>();'], 'Web AddCoreServices registers IBasketService and IOrderService with scoped BasketService and OrderService implementations.', 'CONFIRMED'),
('web.repositories','src/Web/Configuration/ConfigureCoreServices.cs',['services.AddScoped(typeof(IReadRepository<>), typeof(EfRepository<>));','services.AddScoped(typeof(IRepository<>), typeof(EfRepository<>));'], 'Web registers scoped generic IReadRepository and IRepository implementations as EfRepository.', 'CONFIRMED'),
('api.endpoints','src/PublicApi/Program.cs',['builder.Services.AddFastEndpoints();','app.UseFastEndpoints();'], 'PublicApi registers FastEndpoints services and adds FastEndpoints to its middleware pipeline.', 'CONFIRMED'),
('persistence.inmemory','src/Infrastructure/Dependencies.cs',['if (useOnlyInMemoryDatabase)','options.UseInMemoryDatabase("Catalog"));','options.UseInMemoryDatabase("Identity"));'], 'Infrastructure ConfigureLocalDatabaseContexts selects Catalog and Identity in-memory databases when UseOnlyInMemoryDatabase is true.', 'CONFIRMED'),
('order.rationale','src/ApplicationCore/Services/OrderService.cs',['var orderItem = new OrderItem(itemOrdered, basketItem.UnitPrice, basketItem.Quantity);'], 'OrderItem snapshots may be intended to preserve historical checkout prices; business rationale is inferred and not established by source.', 'INFERRED'),
]

# Manually reviewed expected supporting sets. Queries do not embed record IDs.
QUESTIONS=[
('How does AddItemToBasket handle a null basket lookup?', ['eshop.basket.create'],False),
('How does Basket AddItem handle an existing matching CatalogItemId?', ['eshop.basket.merge'],False),
('What guards prevent empty basket checkout?', ['eshop.order.guard'],False),
('When does OrderService publish OrderCreatedEvent?', ['eshop.order.publish'],False),
('What does EfRepository implement?', ['eshop.persistence.repository'],False),
('How does PublicApi wire FastEndpoints?', ['eshop.api.endpoints'],False),
('What does UseOnlyInMemoryDatabase select?', ['eshop.persistence.inmemory'],False),
('How are satellite telemetry encryption keys rotated?', [],False),
('Are historical checkout prices the business rationale for OrderItem snapshots?', ['eshop.order.rationale'],True),
]


def dataset(root):
    records=[]; evidence_map=[]
    for name,path,anchors,statement,status in SPECS:
        raw=(Path(root)/path).read_bytes(); lines=raw.decode('utf-8-sig').splitlines()
        positions=[]
        for anchor in anchors:
            found=[i+1 for i,line in enumerate(lines) if line.strip()==anchor]
            if not found: found=[i+1 for i,line in enumerate(lines) if anchor in line]
            assert len(found)==1,(path,anchor,found)
            positions.extend(found)
        cid='eshop.'+name; eid='evidence.'+cid
        prov={'actor':'p0-source-review','method':f'curated source observation at {PIN}; rationale explicitly inferred where labeled'}
        claim={'id':cid,'statement':statement,'type':'technical_fact','status':status,
               'evidence':[eid],'provenance':prov,'last_verified':'2026-11-14' if status=='CONFIRMED' else None,
               'depends_on':[],'conflicts_with':[]}
        evidence={'id':eid,'type':'direct-technical' if status=='CONFIRMED' else 'derived','status':'active',
                  'source':path,'provenance':prov,'captured_at':'2026-11-14T00:00:00Z',
                  'location':f'{path}#L{min(positions)}-L{max(positions)}@{PIN}',
                  'content_hash':'sha256:'+hashlib.sha256(raw).hexdigest(),
                  'description':f'Source anchors at revision {PIN}: '+ ' | '.join(anchors), 'substantiates':[cid]}
        records.append({'version':1,'operation':'add','records':{'claims':[claim],'evidence':[evidence],'relationships':[]}})
        evidence_map.append({'claim':cid,'path':path,'lines':positions,'anchors':anchors,'revision':PIN,'sha256':evidence['content_hash']})
    return records,evidence_map
