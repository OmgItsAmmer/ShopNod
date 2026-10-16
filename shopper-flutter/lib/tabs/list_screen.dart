import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../state/app_controller.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';

class ListScreen extends ConsumerStatefulWidget {
  const ListScreen({super.key});
  @override
  ConsumerState<ListScreen> createState() => _ListScreenState();
}

class _ListScreenState extends ConsumerState<ListScreen> {
  final controller = TextEditingController();
  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final app = ref.watch(appControllerProvider);
    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: PageFrame(
            maxWidth: 760,
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'My shopping list',
                  style: Theme.of(context).textTheme.headlineLarge,
                ),
                const SizedBox(height: 6),
                Text(
                  'Items help us find useful offers. Your list is deleted after 30 days.',
                  style: TextStyle(color: context.tokens.textMuted),
                ),
                const SizedBox(height: 22),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: controller,
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _add(app),
                        decoration: const InputDecoration(
                          hintText: 'Add bread, milk, rice…',
                          prefixIcon: Icon(Icons.add_shopping_cart_outlined),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    IconButton.filled(
                      onPressed: () => _add(app),
                      icon: const Icon(Icons.add),
                      tooltip: 'Add item',
                      style: IconButton.styleFrom(
                        minimumSize: const Size(56, 56),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        if (!app.consents.list)
          const SliverFillRemaining(
            child: EmptyState(
              icon: Icons.lock_outline,
              title: 'Shopping list is off',
              message:
                  'Turn on Shopping list consent in Settings to save items.',
            ),
          )
        else if (app.shoppingList.isEmpty)
          const SliverFillRemaining(
            child: EmptyState(
              icon: Icons.playlist_add_rounded,
              title: 'Your list is empty',
              message:
                  'Add what you need and matching offers will move up your feed.',
            ),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
            sliver: SliverList.builder(
              itemCount: app.shoppingList.length,
              itemBuilder: (ctx, i) => Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 720),
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 9),
                    child: Card(
                      child: ListTile(
                        minTileHeight: 64,
                        leading: Container(
                          width: 38,
                          height: 38,
                          decoration: BoxDecoration(
                            color: context.tokens.primary.withValues(
                              alpha: .12,
                            ),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Icon(
                            Icons.shopping_basket_outlined,
                            color: context.tokens.primary,
                            size: 20,
                          ),
                        ),
                        title: Text(
                          app.shoppingList[i],
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.close),
                          tooltip: 'Remove',
                          onPressed: () {
                            final items = [...app.shoppingList]..removeAt(i);
                            app.saveShoppingList(items);
                          },
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  void _add(AppController app) {
    final value = controller.text.trim();
    if (value.isEmpty) return;
    app.saveShoppingList([...app.shoppingList, value]);
    controller.clear();
  }
}
