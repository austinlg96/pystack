from pathlib import Path
from unittest.mock import mock_open
from unittest.mock import patch

import pytest

from pystack.errors import MissingExecutableMaps
from pystack.errors import ProcessNotFound
from pystack.errors import PystackError
from pystack.maps import VirtualMap
from pystack.maps import generate_maps_for_process
from pystack.maps import parse_maps_file_for_binary


def test_virtual_map():
    # GIVEN

    map = VirtualMap(
        start=0,
        end=10,
        offset=1234,
        device="device",
        flags="xrwp",
        inode=42,
        path=None,
        filesize=10,
    )

    # WHEN / THEN

    assert map.contains(5)
    assert not map.contains(15)
    assert map.is_private()
    assert map.is_executable()
    assert map.is_readable()
    assert map.is_writable()


def test_simple_maps_no_such_pid():
    # GIVEN

    with patch("builtins.open", side_effect=FileNotFoundError()):

        # WHEN / THEN
        with pytest.raises(ProcessNotFound):
            list(generate_maps_for_process(1))


def test_simple_maps():
    # GIVEN

    map_text = """
7f1ac1e2b000-7f1ac1e50000 r--p 00000000 08:12 8398159                    /usr/lib/libc-2.31.so
    """

    # WHEN

    with patch("builtins.open", mock_open(read_data=map_text)):
        maps = list(generate_maps_for_process(1))

    # THEN

    assert maps == [
        VirtualMap(
            start=139752898736128,
            end=139752898887680,
            filesize=151552,
            offset=0,
            device="08:12",
            flags="r--p",
            inode=8398159,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]


def test_maps_with_long_device_numbers():
    # GIVEN

    map_text = """
7f1ac1e2b000-7f1ac1e50000 r--p 00000000 0123:4567 8398159 /usr/lib/libc-2.31.so
    """

    # WHEN

    with patch("builtins.open", mock_open(read_data=map_text)):
        maps = list(generate_maps_for_process(1))

    # THEN

    assert maps == [
        VirtualMap(
            start=139752898736128,
            end=139752898887680,
            filesize=151552,
            offset=0,
            device="0123:4567",
            flags="r--p",
            inode=8398159,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]


def test_anonymous_maps():
    # GIVEN

    map_text = """
7f1ac1e2b000-7f1ac1e50000 r--p 00000000 08:12 8398159
    """

    # WHEN

    with patch("builtins.open", mock_open(read_data=map_text)):
        maps = list(generate_maps_for_process(1))

    # THEN

    assert maps == [
        VirtualMap(
            start=139752898736128,
            end=139752898887680,
            filesize=151552,
            offset=0,
            device="08:12",
            flags="r--p",
            inode=8398159,
            path=None,
        ),
    ]


def test_map_permissions():
    # GIVEN

    map_text = """
7f1ac1e2b000-7f1ac1e50000 r--- 00000000 08:12 8398159                    /usr/lib/libc-2.31.so
7f1ac1e2b000-7f1ac1e50000 rw-- 00000000 08:12 8398159                    /usr/lib/libc-2.31.so
7f1ac1e2b000-7f1ac1e50000 rwx- 00000000 08:12 8398159                    /usr/lib/libc-2.31.so
7f1ac1e2b000-7f1ac1e50000 rwxp 00000000 08:12 8398159                    /usr/lib/libc-2.31.so
    """

    # WHEN

    with patch("builtins.open", mock_open(read_data=map_text)):
        maps = list(generate_maps_for_process(1))

    # THEN

    assert maps == [
        VirtualMap(
            start=139752898736128,
            end=139752898887680,
            filesize=151552,
            offset=0,
            device="08:12",
            flags="r---",
            inode=8398159,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
        VirtualMap(
            start=139752898736128,
            end=139752898887680,
            filesize=151552,
            offset=0,
            device="08:12",
            flags="rw--",
            inode=8398159,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
        VirtualMap(
            start=139752898736128,
            end=139752898887680,
            filesize=151552,
            offset=0,
            device="08:12",
            flags="rwx-",
            inode=8398159,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
        VirtualMap(
            start=139752898736128,
            end=139752898887680,
            filesize=151552,
            offset=0,
            device="08:12",
            flags="rwxp",
            inode=8398159,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]


def test_unexpected_line_is_ignored():
    # GIVEN

    map_text = """
I am an unexpected line
7f1ac1e2b000-7f1ac1e50000 r--p 00000000 08:12 8398159                    /usr/lib/libc-2.31.so
    """

    # WHEN

    with patch("builtins.open", mock_open(read_data=map_text)):
        maps = list(generate_maps_for_process(1))

    # THEN

    assert maps == [
        VirtualMap(
            start=139752898736128,
            end=139752898887680,
            filesize=151552,
            offset=0,
            device="08:12",
            flags="r--p",
            inode=8398159,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]


def test_special_maps():
    # GIVEN

    map_text = """
555f1ab1c000-555f1ab3d000 rw-p 00000000 00:00 0                          [heap]
7ffdf8102000-7ffdf8124000 rw-p 00000000 00:00 0                          [stack]
7ffdf8152000-7ffdf8155000 r--p 00000000 00:00 0                          [vvar]
7ffdf8155000-7ffdf8156000 r-xp 00000000 00:00 0                          [vdso]
ffffffffff600000-ffffffffff601000 --xp 00000000 00:00 0                  [vsyscall]
    """

    # WHEN

    with patch("builtins.open", mock_open(read_data=map_text)):
        maps = list(generate_maps_for_process(1))

    # THEN

    assert maps == [
        VirtualMap(
            start=93866958110720,
            end=93866958245888,
            filesize=135168,
            offset=0,
            device="00:00",
            flags="rw-p",
            inode=0,
            path=Path("[heap]"),
        ),
        VirtualMap(
            start=140728765259776,
            end=140728765399040,
            filesize=139264,
            offset=0,
            device="00:00",
            flags="rw-p",
            inode=0,
            path=Path("[stack]"),
        ),
        VirtualMap(
            start=140728765587456,
            end=140728765599744,
            filesize=12288,
            offset=0,
            device="00:00",
            flags="r--p",
            inode=0,
            path=Path("[vvar]"),
        ),
        VirtualMap(
            start=140728765599744,
            end=140728765603840,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="r-xp",
            inode=0,
            path=Path("[vdso]"),
        ),
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("[vsyscall]"),
        ),
    ]


def test_maps_for_binary_only_python_exec():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    maps = [
        python,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.python == python
    assert mapinfo.libpython is None
    assert mapinfo.bss is None
    assert mapinfo.heap is None


def test_maps_for_binary_with_heap():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    heap = VirtualMap(
        start=140728765587456,
        end=140728765599744,
        filesize=12288,
        offset=0,
        device="00:00",
        flags="r--p",
        inode=0,
        path=Path("[heap]"),
    )

    maps = [
        python,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
        heap,
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.python == python
    assert mapinfo.libpython is None
    assert mapinfo.bss is None
    assert mapinfo.heap == heap


def test_maps_for_binary_with_libpython():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    libpython = VirtualMap(
        start=140728765587456,
        end=140728765599744,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r--p",
        inode=0,
        path=Path("/some/path/to/libpython.so"),
    )

    maps = [
        python,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
        libpython,
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.python == python
    assert mapinfo.libpython == libpython
    assert mapinfo.bss is None
    assert mapinfo.heap is None


def test_maps_for_binary_executable_with_bss():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    bss = VirtualMap(
        start=139752898736128,
        end=139752898887680,
        filesize=4096,
        offset=0,
        device="08:12",
        flags="r--p",
        inode=8398159,
        path=None,
    )

    maps = [
        python,
        bss,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.python == python
    assert mapinfo.libpython is None
    assert mapinfo.bss == bss
    assert mapinfo.heap is None


def test_maps_for_binary_libpython_with_bss():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    bss = VirtualMap(
        start=139752898736128,
        end=139752898887680,
        filesize=4096,
        offset=0,
        device="08:12",
        flags="r--p",
        inode=8398159,
        path=None,
    )

    libpython = VirtualMap(
        start=140728765587456,
        end=140728765599744,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r--p",
        inode=0,
        path=Path("/some/path/to/libpython.so"),
    )

    libpyhon_bss = VirtualMap(
        start=18446744073699065856,
        end=18446744073699069952,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=None,
    )

    maps = [
        python,
        bss,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
        libpython,
        libpyhon_bss,
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.python == python
    assert mapinfo.libpython == libpython
    assert mapinfo.bss == libpyhon_bss
    assert mapinfo.heap is None


def test_maps_for_binary_libpython_without_bss():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    bss = VirtualMap(
        start=139752898736128,
        end=139752898887680,
        filesize=4096,
        offset=0,
        device="08:12",
        flags="r--p",
        inode=8398159,
        path=None,
    )

    libpython = VirtualMap(
        start=140728765587456,
        end=140728765599744,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r--p",
        inode=0,
        path=Path("/some/path/to/libpython.so"),
    )

    maps = [
        python,
        bss,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
        libpython,
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.python == python
    assert mapinfo.libpython == libpython
    assert mapinfo.bss is None
    assert mapinfo.heap is None


def test_maps_for_binary_libpython_with_bss_with_non_readable_segment():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    bss = VirtualMap(
        start=139752898736128,
        end=139752898887680,
        filesize=4096,
        offset=0,
        device="08:12",
        flags="r--p",
        inode=8398159,
        path=None,
    )

    libpython = VirtualMap(
        start=140728765587456,
        end=140728765599744,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r--p",
        inode=0,
        path=Path("/some/path/to/libpython.so"),
    )

    libpyhon_bss = VirtualMap(
        start=18446744073699065856,
        end=18446744073699069952,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=None,
    )

    maps = [
        python,
        bss,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
        libpython,
        VirtualMap(
            start=1844674407369906,
            end=18446744073699069,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="---p",
            inode=0,
            path=None,
        ),
        libpyhon_bss,
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.python == python
    assert mapinfo.libpython == libpython
    assert mapinfo.bss == libpyhon_bss
    assert mapinfo.heap is None


def test_maps_for_binary_range():
    # GIVEN

    maps = [
        VirtualMap(
            start=1,
            end=2,
            filesize=1,
            offset=0,
            device="00:00",
            flags="r-xp",
            inode=0,
            path=Path("the_executable"),
        ),
        VirtualMap(
            start=2,
            end=3,
            filesize=1,
            offset=0,
            device="08:12",
            flags="r--p",
            inode=8398159,
            path=None,
        ),
        VirtualMap(
            start=5,
            end=6,
            filesize=1,
            offset=0,
            device="00:00",
            flags="r--p",
            inode=0,
            path=Path("/some/path/to/libpython.so"),
        ),
        VirtualMap(
            start=8,
            end=9,
            filesize=1,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=None,
        ),
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.memory.min_addr == 1
    assert mapinfo.memory.max_addr == 9


def test_maps_for_binary_range_vmaps_are_ignored():
    # GIVEN

    maps = [
        VirtualMap(
            start=1,
            end=2,
            filesize=1,
            offset=0,
            device="00:00",
            flags="r-xp",
            inode=0,
            path=Path("the_executable"),
        ),
        VirtualMap(
            start=2000,
            end=3000,
            filesize=1000,
            offset=0,
            device="08:12",
            flags="r--p",
            inode=8398159,
            path=Path("[vsso]"),
        ),
        VirtualMap(
            start=5,
            end=6,
            filesize=1,
            offset=0,
            device="00:00",
            flags="r--p",
            inode=0,
            path=Path("[vsyscall]"),
        ),
        VirtualMap(
            start=8,
            end=9,
            filesize=1,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("[vvar]"),
        ),
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.memory.min_addr == 1
    assert mapinfo.memory.max_addr == 2


def test_maps_for_binary_no_binary_map():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    maps = [
        python,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]

    # WHEN / THEN

    with pytest.raises(MissingExecutableMaps):
        parse_maps_file_for_binary(Path("another_executable"), maps)


def test_maps_for_binary_no_executable_segment():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r--p",
        inode=0,
        path=Path("the_executable"),
    )

    maps = [
        python,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]

    # WHEN

    mapinfo = parse_maps_file_for_binary(Path("the_executable"), maps)

    # THEN

    assert mapinfo.python == python
    assert mapinfo.libpython is None
    assert mapinfo.bss is None
    assert mapinfo.heap is None


def test_maps_for_binary_multiple_libpythons():
    # GIVEN

    maps = [
        VirtualMap(
            start=140728765599744,
            end=140728765603840,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="r--p",
            inode=0,
            path=Path("the_executable"),
        ),
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libpython3.8.so"),
        ),
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libpython2.7.so"),
        ),
    ]

    # WHEN / THEN

    with pytest.raises(PystackError):
        parse_maps_file_for_binary(Path("the_executable"), maps)


def test_maps_for_binary_invalid_executable():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=Path("the_executable"),
    )

    maps = [
        python,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]

    # WHEN

    with pytest.raises(MissingExecutableMaps, match="the_executable"):
        parse_maps_file_for_binary(Path("other_executable"), maps)


def test_maps_for_binary_invalid_executable_and_no_available_maps():
    # GIVEN

    python = VirtualMap(
        start=140728765599744,
        end=140728765603840,
        filesize=4096,
        offset=0,
        device="00:00",
        flags="r-xp",
        inode=0,
        path=None,
    )

    maps = [
        python,
        VirtualMap(
            start=18446744073699065856,
            end=18446744073699069952,
            filesize=4096,
            offset=0,
            device="00:00",
            flags="--xp",
            inode=0,
            path=Path("/usr/lib/libc-2.31.so"),
        ),
    ]

    # WHEN

    with pytest.raises(
        MissingExecutableMaps, match="There are no available executable maps"
    ):
        parse_maps_file_for_binary(Path("other_executable"), maps)


def test_maps_with_scattered_segments():
    map_text = """
00400000-00401000 r-xp 00000000 fd:00 67488961          /bin/python3.9-dbg
00600000-00601000 r--p 00000000 fd:00 67488961          /bin/python3.9-dbg
00601000-00602000 rw-p 00001000 fd:00 67488961          /bin/python3.9-dbg
0067b000-00a58000 rw-p 00000000 00:00 0                 [heap]
7f7b38000000-7f7b38028000 rw-p 00000000 00:00 0
7f7b38028000-7f7b3c000000 ---p 00000000 00:00 0
7f7b40000000-7f7b40021000 rw-p 00000000 00:00 0
7f7b40021000-7f7b44000000 ---p 00000000 00:00 0
7f7b44ec0000-7f7b44f40000 rw-p 00000000 00:00 0
f7b45a61000-7f7b45d93000 rw-p 00000000 00:00 0
7f7b46014000-7f7b46484000 r--p 0050b000 fd:00 1059871   /lib64/libpython3.9d.so.1.0
7f7b46484000-7f7b46485000 ---p 00000000 00:00 0
7f7b46485000-7f7b46cda000 rw-p 00000000 00:00 0
7f7b46cda000-7f7b46d16000 r--p 00a3d000 fd:00 1059871   /lib64/libpython3.9d.so.1.0
7f7b46d16000-7f7b46d6f000 rw-p 00000000 00:00 0
7f7b46d6f000-7f7b46d92000 r--p 00001000 fd:00 67488961  /bin/python3.9-dbg
7f7b46d92000-7f7b46d93000 ---p 00000000 00:00 0
7f7b46d93000-7f7b475d3000 rw-p 00000000 00:00 0
7f7b498c1000-7f7b49928000 r-xp 00000000 fd:00 7023      /lib64/libssl.so.1.0.0
7f7b49928000-7f7b49b28000 ---p 00067000 fd:00 7023      /lib64/libssl.so.1.0.0
f7b4c632000-7f7b4c6f3000 rw-p 00000000 00:00 0
7f7b4c6f3000-7f7b4c711000 rw-p 00000000 00:00 0
7f7b4c711000-7f7b4c712000 r--p 0002a000 fd:00 67488961  /bin/python3.9-dbg
7f7b4c712000-7f7b4c897000 rw-p 00000000 00:00 0
7f7b5a356000-7f7b5a35d000 r--s 00000000 fd:00 201509519 /usr/lib64/gconv/gconv-modules.cache
7f7b5a35d000-7f7b5a827000 r-xp 00000000 fd:00 1059871   /lib64/libpython3.9d.so.1.0
7f7b5a827000-7f7b5aa27000 ---p 004ca000 fd:00 1059871   /lib64/libpython3.9d.so.1.0
7f7b5aa27000-7f7b5aa2c000 r--p 004ca000 fd:00 1059871   /lib64/libpython3.9d.so.1.0
7f7b5aa2c000-7f7b5aa67000 rw-p 004cf000 fd:00 1059871   /lib64/libpython3.9d.so.1.0
7f7b5aa67000-7f7b5aa8b000 rw-p 00000000 00:00 0
7fff26f8e000-7fff27020000 rw-p 00000000 00:00 0         [stack]
7fff27102000-7fff27106000 r--p 00000000 00:00 0         [vvar]
7fff27106000-7fff27108000 r-xp 00000000 00:00 0         [vdso]
ffffffffff600000-ffffffffff601000 r-xp 00000000 00:00 0 [vsyscall]
    """

    # WHEN

    with patch("builtins.open", mock_open(read_data=map_text)):
        maps = list(generate_maps_for_process(1))

    mapinfo = parse_maps_file_for_binary(Path("/bin/python3.9-dbg"), maps)

    # THEN

    assert mapinfo.python == VirtualMap(
        start=0x400000,
        end=0x401000,
        filesize=4096,
        offset=0,
        device="fd:00",
        flags="r-xp",
        inode=67488961,
        path=Path("/bin/python3.9-dbg"),
    )
    assert mapinfo.libpython == VirtualMap(
        start=0x7F7B46014000,
        end=0x7F7B46484000,
        filesize=4653056,
        offset=5287936,
        device="fd:00",
        flags="r--p",
        inode=1059871,
        path=Path("/lib64/libpython3.9d.so.1.0"),
    )
    assert mapinfo.bss == VirtualMap(
        start=140167436849152,
        end=140167445585920,
        filesize=8736768,
        offset=0,
        device="00:00",
        flags="rw-p",
        inode=0,
        path=None,
    )
    assert mapinfo.heap == VirtualMap(
        start=0x0067B000,
        end=0x00A58000,
        filesize=4050944,
        offset=0,
        device="00:00",
        flags="rw-p",
        inode=0,
        path=Path("[heap]"),
    )
