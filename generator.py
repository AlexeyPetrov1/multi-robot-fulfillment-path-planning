'''это файл генератора начальных условий, код решателя в test_run.py

graph.txt устроен следующим образом:
в первой строке 2 числа через пробел

<число вершин> <число рёбер>
далее в <число рёбер> строках записано по 2 числа через пробел:
<вершина_1> <вершина_2> — обозначает, что <вершина_1> и <вершина_2> соединены неориентированным ребром
'''
import random
import matplotlib.pyplot as plt
from collections import deque

def node(i, m, j):
        return i * m + j

def is_border(i, j, n, m, padding):
    return (
      i < padding or i >= n - padding
      or j < padding or j >= m - padding
  )

def generate_graph(n=15, m=20, padding=3, remove_prob=0.05, min_weight=1, max_weight=1, seed=42):
    rng = random.Random(seed)
    if n < 1 or m < 1:
        raise ValueError("n и m должны быть положительными")
    if not 0 <= remove_prob <= 1:
        raise ValueError("remove_prob должен быть от 0 до 1")
    if padding < 0:
        raise ValueError("padding не может быть отрицательным")
    if min_weight < 1 or max_weight < min_weight:
        raise ValueError("Некорректные веса")


    adj = {v: set() for v in range(n * m)}
    edges = []

    for i in range(n):
        for j in range(m):
            u = node(i, m, j)

            for di, dj in [(1, 0), (0, 1)]:
                ni, nj = i + di, j + dj

                if ni >= n or nj >= m:
                    continue

                v = node(ni, m, nj)
                adj[u].add(v)
                adj[v].add(u)

                protected = (
                    is_border(i, j, n,m, padding)
                    or is_border(ni, nj, n,m,padding)
                )

                edges.append((u, v, protected))


    def connected():
        visited = {0}
        queue = deque([0])

        while queue:
            u = queue.popleft()

            for v in adj[u]:
                if v not in visited:
                    visited.add(v)
                    queue.append(v)

        return len(visited) == n * m

    candidates = [
        (u, v) for u, v, protected in edges
        if not protected
    ]
    rng.shuffle(candidates)

    for u, v in candidates:
        if rng.random() >= remove_prob:
            continue

        adj[u].remove(v)
        adj[v].remove(u)

        if not connected():
            adj[u].add(v)
            adj[v].add(u)

    graph = {v: [] for v in adj}

    for u in adj:
        for v in sorted(adj[u]):
            if u < v:
                w = rng.randint(min_weight, max_weight)
                graph[u].append((v, w))
                graph[v].append((u, w))

    for v in graph:
        graph[v].sort()

    unique_edges = []
    for u in adj:
        for v in adj[u]:
            if u < v:
                unique_edges.append((u, v))
    unique_edges.sort()

    V = len(graph)
    E = len(unique_edges)

    with open("graph.txt", "w", encoding="utf-8") as f:
        f.write(f"{V} {E}\n")
        for u, v in unique_edges:
            f.write(f"{u} {v}\n")

    return graph

import random

def generate_tasks(graph, num_tasks=10, seed=42):
    rng = random.Random(seed)
    nodes = list(graph.keys())

    tasks = []
    for i in range(num_tasks):
        A, B = rng.sample(nodes, 2)
        tasks.append({"id": i,"A": A,"B": B})

    with open("graph.txt", "a", encoding="utf-8") as f:
            f.write('\n')
            for task in tasks:
                i, A, B = task['id'], task['A'], task['B']
                f.write(f"{i}: {A} {B}\n")
    return tasks


def visualize_graph(graph, n, m, padding=3):
    return
    plt.figure(figsize=(12, 8))

    for u, neighbors in graph.items():
        x1, y1 = u % m, u // m

        for v, _ in neighbors:
            if u >= v:
                continue

            x2, y2 = v % m, v // m

            plt.plot(
                [x1, x2], [y1, y2],
                color="gray", linewidth=1.5, zorder=1
            )

    for u in graph:
        x, y = u % m, u // m

        border = (
            y < padding or y >= n - padding
            or x < padding or x >= m - padding
        )

        plt.scatter(
            x, y,
            color="royalblue" if border else "darkorange",
            s=45, zorder=2
        )

    plt.gca().invert_yaxis()
    plt.axis("equal")
    plt.grid(alpha=0.15)
    plt.title(f"Случайный связный граф {n}×{m}, padding={padding}")
    plt.show()



if __name__ == "__main__":
    n = 15
    m = 20
    padding = 3
    remove_prob = 0.2

    graph = generate_graph(
        n=n,
        m=m,
        padding=padding,
        remove_prob=remove_prob,
        seed=42
    )


    for v in list(graph)[:15]:
        print(f"{v}: {graph[v]}")

    print(f"\nУзлов: {len(graph)}")
    print(f"Рёбер: {sum(len(x) for x in graph.values()) // 2}")


    with open("graph.txt", "w", encoding="utf-8") as f:
        for v, neighbors in graph.items():
            f.write(f"{v} {neighbors}\n")

    visualize_graph(graph, n, m, padding)

    

    tasks = generate_tasks(graph, num_tasks=10)

    for task in tasks:
        print(task)

